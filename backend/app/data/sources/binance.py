from datetime import UTC, datetime

import httpx
import pandas as pd

from app.data.models import Timeframe, empty_ohlcv, normalize_ohlcv
from app.data.ratelimit import RateLimiter
from app.data.sources.base import SourceError

# Endpoint pubblico di sola lettura per i dati di mercato: niente chiave, peso basso.
BASE_URL = "https://data-api.binance.vision"
PAGE_LIMIT = 1000


class BinanceSource:
    name = "binance"

    def __init__(self, client: httpx.Client, limiter: RateLimiter | None = None) -> None:
        self.client = client
        self.limiter = limiter or RateLimiter(capacity=10, per_seconds=1)

    def available(self) -> bool:
        return True

    def max_history(self, timeframe: Timeframe) -> pd.Timedelta | None:
        return None

    def fetch(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        if not timeframe.stored:
            raise ValueError(f"timeframe non scaricabile: {timeframe}")
        rows: list[list[object]] = []
        cursor = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        while cursor < end_ms:
            self.limiter.acquire()
            try:
                response = self.client.get(
                    f"{BASE_URL}/api/v3/klines",
                    params={
                        "symbol": symbol,
                        "interval": timeframe.value,
                        "startTime": cursor,
                        "endTime": end_ms - 1,
                        "limit": PAGE_LIMIT,
                    },
                    timeout=20,
                )
                response.raise_for_status()
                page = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise SourceError(f"binance {symbol} {timeframe}: {exc}") from exc
            if not isinstance(page, list):
                raise SourceError(f"binance {symbol}: risposta inattesa")
            if not page:
                break
            rows.extend(page)
            last_open = int(page[-1][0])
            next_cursor = last_open + timeframe.minutes * 60_000
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            if len(page) < PAGE_LIMIT:
                break
        return parse_klines(rows, now=datetime.now(UTC), timeframe=timeframe)


def parse_klines(rows: list[list[object]], now: datetime, timeframe: Timeframe) -> pd.DataFrame:
    """Converte le kline Binance; scarta la candela ancora aperta."""
    if not rows:
        return empty_ohlcv()
    frame = pd.DataFrame(
        [r[:6] for r in rows], columns=["ts", "open", "high", "low", "close", "volume"]
    )
    frame["ts"] = pd.to_datetime(frame["ts"].astype("int64"), unit="ms", utc=True)
    frame = frame.set_index("ts")
    closed = frame.index + pd.Timedelta(minutes=timeframe.minutes) <= pd.Timestamp(now)
    return normalize_ohlcv(frame[closed])
