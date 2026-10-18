from collections.abc import Iterator
from datetime import UTC, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, select

from app.api import deps
from app.data.models import Timeframe
from app.db import repository as repo
from app.db.schema import trade_ideas, trades
from app.jobs import trading as trading_job
from app.jobs.prices import run_update
from app.main import app
from tests.conftest import ohlcv
from tests.test_db_api import FakeRegistry

NOW = datetime(2026, 10, 17, 12, tzinfo=UTC)


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    def conn() -> Iterator[Connection]:
        with engine.connect() as c:
            yield c

    app.dependency_overrides[deps.get_conn] = conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def strong_signal(engine: Engine, symbol: str, horizon: str, score: float) -> datetime:
    with engine.begin() as conn:
        ids = repo.instrument_ids(conn)
        frame = repo.load_prices(conn, ids[symbol], Timeframe.D1, limit=1)
        ts = frame.index[-1].to_pydatetime()
        repo.replace_signals(
            conn,
            ids[symbol],
            horizon,
            [
                {
                    "ts": ts,
                    "score": score,
                    "components": {"trend": 0.9},
                    "favorable": [
                        {
                            "key": "price_anchor",
                            "component": "trend",
                            "label": "Prezzo sopra la media lenta",
                            "value": 0.9,
                        }
                    ],
                    "contrary": [],
                    "risk_label": "Medio",
                }
            ],
            keep=5,
        )
    return ts


def test_correlated_candidates_are_rejected(engine: Engine, client: TestClient) -> None:
    # Le serie finte sono identiche: correlazione 1, quindi una sola proposta.
    run_update(engine, FakeRegistry(), now=NOW)
    for symbol in ("SPX", "NDX"):
        strong_signal(engine, symbol, "swing", 60.0)
    assert trading_job.run(engine, now=NOW, send=False)["proposte"] == 1
    reasons = [s["reason"] for s in client.get("/api/today").json()["skipped"]]
    assert any(r.startswith("Troppo correlato") for r in reasons)


def test_proposals_simulation_and_journal(
    engine: Engine, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.trading import engine as trading_engine

    monkeypatch.setattr(trading_engine, "correlations", lambda conn, s, others: {})
    run_update(engine, FakeRegistry(), now=NOW)
    for symbol in ("SPX", "NDX", "SOX", "NDX2L"):
        strong_signal(engine, symbol, "swing", 60.0)

    counts = trading_job.run(engine, now=NOW, send=False)
    assert counts["proposte"] == 3  # massimo 3 tra posizioni e proposte

    with engine.connect() as conn:
        ideas = conn.execute(select(trade_ideas)).mappings().all()
    assert all(i["risk_eur"] <= 10.0 + 1e-6 for i in ideas)
    assert all(i["stop"] < i["entry"] < i["target"] for i in ideas)
    assert all("\n" in i["motivation"] for i in ideas)

    today = client.get("/api/today").json()
    assert len(today["proposals"]) == 3
    assert today["open_positions"] == 3
    assert any("3 posizioni" in s["reason"] for s in today["skipped"])

    # Rieseguire non duplica le proposte dello stesso segnale.
    assert trading_job.run(engine, now=NOW, send=False)["proposte"] == 0

    # Nuova candela che scende sotto lo stop: la simulazione apre e chiude in perdita.
    btc = next(i for i in ideas if i["instrument_id"] == _id(engine, "SPX"))
    nxt = pd.DatetimeIndex([pd.Timestamp(btc["signal_ts"]) + pd.Timedelta(days=1)])
    with engine.begin() as conn:
        bar = ohlcv(nxt, [btc["entry"]])
        bar["low"] = btc["stop"] * 0.98
        repo.upsert_prices(conn, _id(engine, "SPX"), Timeframe.D1, bar, "prova")
    counts = trading_job.run(engine, now=NOW, send=False)
    assert counts["aperti"] >= 1 and counts["chiusi"] >= 1

    with engine.connect() as conn:
        closed = conn.execute(select(trades).where(trades.c.status == "chiusa")).mappings().all()
    assert closed[0]["exit_reason"] == "stop"
    assert -10.5 < closed[0]["pnl_eur"] < -9.0  # perdita vicina all'1% del capitale, costi inclusi

    journal = client.get("/api/journal").json()
    assert journal["stats"]["trades"] == 1
    assert journal["stats"]["win_rate"] == 0.0
    assert journal["stats"]["max_drawdown"] < 0

    portfolio = client.get("/api/portfolio").json()
    assert portfolio["equity"] < 1000
    assert portfolio["lev3_limit"] == pytest.approx(0.3 * portfolio["equity"], rel=1e-3)


def test_daily_loss_blocks_new_proposals(engine: Engine, client: TestClient) -> None:
    run_update(engine, FakeRegistry(), now=NOW)
    with engine.begin() as conn:
        ids = repo.instrument_ids(conn)
        idea_id = conn.execute(
            trade_ideas.insert()
            .values(
                instrument_id=ids["ETH"],
                horizon="swing",
                signal_ts=NOW,
                score=50,
                entry=100,
                stop=95,
                target=110,
                size_eur=200,
                risk_eur=10,
                costs_eur=1,
                risk_label="Medio",
                motivation="prova\nprova",
                expires_at=NOW,
                status="chiusa",
            )
            .returning(trade_ideas.c.id)
        ).scalar_one()
        conn.execute(
            trades.insert().values(
                idea_id=idea_id,
                entry_ts=NOW,
                entry_price=100,
                size_eur=200,
                exit_ts=datetime.now(UTC),
                exit_price=80,
                exit_reason="stop",
                pnl_eur=-40,
                fees_eur=1,
                status="chiusa",
            )
        )
    strong_signal(engine, "SPX", "swing", 60.0)
    assert trading_job.run(engine, now=NOW, send=False)["proposte"] == 0
    today = client.get("/api/today").json()
    assert today["daily_limit_reached"] is True


def _id(engine: Engine, symbol: str) -> int:
    with engine.connect() as conn:
        return repo.instrument_ids(conn)[symbol]
