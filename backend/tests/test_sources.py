import json
from datetime import UTC, datetime

import httpx
import pandas as pd
import pytest

from app.data.models import Timeframe
from app.data.ratelimit import RateLimiter
from app.data.sources.base import SourceError, SourceUnavailableError
from app.data.sources.binance import BinanceSource, parse_klines
from app.data.sources.registry import SourceRegistry
from app.data.sources.twelvedata import TwelveDataSource, parse_time_series
from app.data.sources.yfinance_source import parse_history
from app.data.universe import Calendar, InstrumentSpec, Kind, SourceRef
from tests.conftest import ohlcv

FAST = RateLimiter(capacity=1000, per_seconds=1)


def kline(ms: int, close: float) -> list[object]:
    return [ms, "1", str(close + 1), "0.5", str(close), "10", ms + 1, "0", 1, "0", "0", "0"]


def test_parse_klines_drops_open_candle() -> None:
    day = 86_400_000
    t0 = int(datetime(2026, 10, 15, tzinfo=UTC).timestamp() * 1000)
    rows = [kline(t0, 1.0), kline(t0 + day, 2.0), kline(t0 + 2 * day, 3.0)]
    now = datetime(2026, 10, 17, 12, tzinfo=UTC)
    frame = parse_klines(rows, now=now, timeframe=Timeframe.D1)
    assert frame["close"].tolist() == [1.0, 2.0]  # la candela del 17 è ancora aperta
    assert str(frame.index.tz) == "UTC"


def test_binance_paginates() -> None:
    t0 = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    step = 300_000
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append(params)
        start = int(params["startTime"])
        n = 1000 if len(calls) == 1 else 5
        return httpx.Response(200, json=[kline(start + i * step, 1.0) for i in range(n)])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = BinanceSource(client, FAST)
    end = datetime.fromtimestamp((t0 + 2000 * step) / 1000, tz=UTC)
    frame = source.fetch("BTCUSDT", Timeframe.M5, datetime.fromtimestamp(t0 / 1000, UTC), end)
    assert len(calls) == 2
    assert int(calls[1]["startTime"]) == t0 + 1000 * step
    assert len(frame) == 1005


def test_binance_http_error_becomes_source_error() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(451)))
    with pytest.raises(SourceError):
        BinanceSource(client, FAST).fetch(
            "BTCUSDT", Timeframe.D1, datetime(2026, 1, 1, tzinfo=UTC), datetime.now(UTC)
        )


def test_twelvedata_requires_key() -> None:
    source = TwelveDataSource(httpx.Client(), None)
    assert not source.available()
    with pytest.raises(SourceUnavailableError):
        source.fetch("SPX", Timeframe.D1, datetime(2026, 1, 1, tzinfo=UTC), datetime.now(UTC))


def test_twelvedata_error_never_leaks_key() -> None:
    secret = "-".join(["valore", "finto", "di", "prova"])
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    source = TwelveDataSource(client, secret, FAST)
    with pytest.raises(SourceError) as info:
        source.fetch("SPX", Timeframe.D1, datetime(2026, 1, 1, tzinfo=UTC), datetime.now(UTC))
    assert secret not in str(info.value)
    assert info.value.__cause__ is None


def test_twelvedata_parse() -> None:
    payload = {
        "status": "ok",
        "values": [
            {"datetime": "2026-10-15", "open": "1", "high": "2", "low": "0.5", "close": "1.5"},
            {"datetime": "2026-10-16", "open": "1.5", "high": "2", "low": "1", "close": "1.8"},
        ],
    }
    frame = parse_time_series(json.loads(json.dumps(payload)), "SPX")
    assert frame["close"].tolist() == [1.5, 1.8]
    assert frame["volume"].tolist() == [0.0, 0.0]
    with pytest.raises(SourceError):
        parse_time_series({"status": "error", "code": 429}, "SPX")


def test_yfinance_daily_anchored_to_utc_date() -> None:
    idx = pd.DatetimeIndex(["2026-10-15", "2026-10-16"]).tz_localize("America/New_York")
    raw = pd.DataFrame(
        {
            "Open": [1.0, 2.0],
            "High": [1.5, 2.5],
            "Low": [0.5, 1.5],
            "Close": [1.2, 2.2],
            "Volume": [0, 0],
        },
        index=idx,
    )
    frame = parse_history(raw, Timeframe.D1)
    assert [str(t) for t in frame.index] == [
        "2026-10-15 00:00:00+00:00",
        "2026-10-16 00:00:00+00:00",
    ]


class StubSource:
    def __init__(self, name: str, frame: pd.DataFrame | None, ok: bool = True) -> None:
        self.name = name
        self.frame = frame
        self.ok = ok
        self.calls: list[datetime] = []

    def available(self) -> bool:
        return self.ok

    def max_history(self, timeframe: Timeframe) -> pd.Timedelta | None:
        return pd.Timedelta(days=10) if timeframe.intraday else None

    def fetch(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        self.calls.append(start)
        if self.frame is None:
            raise SourceError(f"{self.name} giù")
        return self.frame


SPEC = InstrumentSpec(
    "XX",
    "Prova",
    Kind.INDEX,
    "USD",
    Calendar.NYSE,
    sources=(SourceRef("a", "A"), SourceRef("b", "B"), SourceRef("c", "C")),
)


def test_registry_falls_back_and_skips_unavailable() -> None:
    idx = pd.date_range("2026-01-01", periods=2, freq="D", tz="UTC")
    data = ohlcv(idx, [1.0, 2.0])
    a = StubSource("a", None)
    b = StubSource("b", data, ok=False)
    c = StubSource("c", data)
    registry = SourceRegistry({"a": a, "b": b, "c": c}, cache=None)
    result = registry.fetch(
        SPEC, Timeframe.D1, datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC)
    )
    assert result.source == "c"
    assert b.calls == []
    assert result.errors == ["a giù"]


def test_registry_respects_max_history() -> None:
    idx = pd.date_range("2026-01-01", periods=2, freq="D", tz="UTC")
    a = StubSource("a", ohlcv(idx, [1.0, 2.0]))
    registry = SourceRegistry({"a": a}, cache=None)
    now = datetime(2026, 3, 1, tzinfo=UTC)
    registry.fetch(SPEC, Timeframe.M5, datetime(2020, 1, 1, tzinfo=UTC), now, now=now)
    assert a.calls == [datetime(2026, 2, 19, tzinfo=UTC)]
