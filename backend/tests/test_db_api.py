from collections.abc import Iterator
from datetime import UTC, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine

from app.api import deps
from app.data.models import Timeframe
from app.data.sources.registry import SourceRegistry
from app.data.universe import UNIVERSE
from app.db import repository as repo
from app.jobs.prices import run_quality, run_update
from app.main import app
from tests.conftest import ohlcv


def test_upsert_is_idempotent_and_updates(engine: Engine) -> None:
    idx = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
    with engine.begin() as conn:
        ids = repo.sync_instruments(conn, UNIVERSE)
        repo.upsert_prices(conn, ids["BTC"], Timeframe.D1, ohlcv(idx, [1.0, 2.0, 3.0]), "t")
        repo.upsert_prices(conn, ids["BTC"], Timeframe.D1, ohlcv(idx[-1:], [4.0]), "t")
        frame = repo.load_prices(conn, ids["BTC"], Timeframe.D1)
        assert frame["close"].tolist() == [1.0, 2.0, 4.0]
        assert repo.load_prices(conn, ids["BTC"], Timeframe.D1, limit=2)["close"].tolist() == [
            2.0,
            4.0,
        ]
        assert repo.last_timestamp(conn, ids["BTC"], Timeframe.D1) == idx[-1].to_pydatetime()
        # Rieseguire la sincronizzazione mantiene gli id.
        assert repo.sync_instruments(conn, UNIVERSE) == ids


def test_symbol_is_parameterized_not_interpolated(engine: Engine) -> None:
    with engine.begin() as conn:
        repo.sync_instruments(conn, UNIVERSE)
        assert repo.instrument_ids(conn)["SPX"] > 0


class FakeRegistry(SourceRegistry):
    def __init__(self) -> None:
        super().__init__({}, cache=None)

    def fetch(self, spec, timeframe, start, end, now=None):  # type: ignore[no-untyped-def]
        from app.data.quality import expected_index
        from app.data.sources.registry import FetchResult

        idx = expected_index(
            spec.calendar,
            timeframe,
            pd.Timestamp(start),
            pd.Timestamp(end) - pd.Timedelta(minutes=timeframe.minutes),
        )
        if timeframe is Timeframe.D1:
            idx = idx[-40:]
        closes = [100.0 + (i % 40) * 0.1 for i in range(len(idx))]
        return FetchResult(ohlcv(idx, closes), "finto", [])


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    def conn() -> Iterator[Connection]:
        with engine.connect() as c:
            yield c

    app.dependency_overrides[deps.get_conn] = conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_update_quality_and_api(engine: Engine, client: TestClient) -> None:
    now = datetime(2026, 10, 17, 12, tzinfo=UTC)  # sabato: mercato USA chiuso
    errors = run_update(engine, FakeRegistry(), now=now)
    assert errors == []
    reports = run_quality(engine, now=now)
    incomplete = [r.summary() for r in reports if r.missing or r.invalid]
    assert incomplete == []

    listing = client.get("/api/instruments").json()
    by_symbol = {i["symbol"]: i for i in listing}
    assert set(by_symbol) == {s.symbol for s in UNIVERSE}
    assert by_symbol["SPX3L"]["synthetic"] and by_symbol["SPX3L"]["underlying"] == "SPX"
    assert by_symbol["SPX"]["change_pct"] == pytest.approx((103.9 / 103.8 - 1) * 100)

    candles = client.get("/api/instruments/SPX3L/candles", params={"timeframe": "1d"}).json()
    assert candles["source"] == "sintetico"
    assert len(candles["candles"]) == 40
    weekly = client.get("/api/instruments/SPX/candles", params={"timeframe": "1w"}).json()
    assert all(pd.Timestamp(c["time"], unit="s").day_name() == "Monday" for c in weekly["candles"])
    assert client.get("/api/instruments/NOPE/candles").status_code == 404
    assert client.get("/api/instruments/SPX/candles", params={"limit": 99999}).status_code == 422
    assert client.get("/api/instruments/sp;x/candles").status_code == 422


def test_indicators_correlations_and_indicator_job(engine: Engine, client: TestClient) -> None:
    from app.jobs import indicators as indicators_job

    now = datetime(2026, 10, 17, 12, tzinfo=UTC)
    run_update(engine, FakeRegistry(), now=now)
    data = client.get("/api/instruments/NDX3L/indicators", params={"limit": 20}).json()
    assert len(data["time"]) == 20
    assert {"sma_20", "rsi_14", "macd", "atr_pct", "decay_annual"} <= set(data["series"])
    assert all(len(v) == 20 for v in data["series"].values())
    assert data["latest"]["decay_annual"] is not None
    assert client.get("/api/instruments/NOPE/indicators").status_code == 404

    corr = client.get("/api/correlations", params={"window": 30}).json()
    assert corr["symbols"] and len(corr["matrix"]) == len(corr["symbols"])
    assert client.get("/api/correlations", params={"window": 5}).status_code == 422

    rows = indicators_job.run(engine)
    assert rows > 0
    with engine.connect() as conn:
        ids = repo.instrument_ids(conn)
        stored = repo.load_indicators(conn, ids["SPX"], Timeframe.D1, ["rsi_14"])
    assert not stored.empty and list(stored.columns) == ["rsi_14"]


def test_sentiment_signals_jobs_and_endpoints(engine: Engine, client: TestClient) -> None:
    from app.jobs import sentiment as sentiment_job
    from app.jobs import signals as signals_job
    from app.sentiment.scorer import LexiconScorer
    from app.sentiment.sources import Item, Target

    class FakeSource:
        name = "news"

        def available(self) -> bool:
            return True

        def fetch(self, target: Target) -> list[Item]:
            return [
                Item(
                    "news",
                    target.symbol,
                    datetime(2026, 10, 16, 12, tzinfo=UTC),
                    "Stocks surge to record highs",
                )
            ]

    run_update(engine, FakeRegistry(), now=datetime(2026, 10, 17, 12, tzinfo=UTC))
    assert sentiment_job.run(engine, [FakeSource()], LexiconScorer()) == 6
    assert signals_job.run(engine) > 0

    signals = client.get("/api/instruments/NDX3S/signals").json()
    assert {s["horizon"] for s in signals} >= {"swing", "day"}
    for s in signals:
        assert -100 <= s["score"] <= 100
        assert s["risk_label"] in {"Alto", "Molto alto"}
        assert all(e["value"] > 0 for e in s["favorable"])
        assert all(e["value"] < 0 for e in s["contrary"])
        assert s["weights"]["trend"] > 0
    under = {s["horizon"]: s["score"] for s in client.get("/api/instruments/NDX/signals").json()}
    for s in signals:
        assert s["score"] == pytest.approx(-under[s["horizon"]], abs=0.11)

    sent = client.get("/api/instruments/NDX3L/sentiment", params={"days": 365}).json()
    assert sent["underlying"] == "NDX"
    assert sent["items"] and sent["items"][0]["score"] == 1.0
    assert len(client.get("/api/signals").json()) >= 14
