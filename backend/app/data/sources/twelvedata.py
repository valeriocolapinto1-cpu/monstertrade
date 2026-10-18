from datetime import datetime

import httpx
import pandas as pd

from app.data.models import Timeframe, empty_ohlcv, normalize_ohlcv
from app.data.ratelimit import RateLimiter
from app.data.sources.base import SourceError, SourceUnavailable

BASE_URL = "https://api.twelvedata.com"
INTERVALS = {Timeframe.M5: "5min", Timeframe.M15: "15min", Timeframe.D1: "1day"}
PAGE_SIZE = 5000


class TwelveDataSource:
    """Piano gratuito: 8 richieste al minuto, 800 al giorno (da verificare sul sito)."""

    name = "twelvedata"

    def __init__(
        self, client: httpx.Client, api_key: str | None, limiter: RateLimiter | None = None
    ) -> None:
        self.client = client
        self._api_key = api_key
        self.limiter = limiter or RateLimiter(capacity=8, per_seconds=60)

    def available(self) -> bool:
        return bool(self._api_key)

    def max_history(self, timeframe: Timeframe) -> pd.Timedelta | None:
        return None

    def fetch(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        if not self._api_key:
            raise SourceUnavailable("TWELVE_DATA_API_KEY non impostata")
        interval = INTERVALS.get(timeframe)
        if interval is None:
            raise ValueError(f"timeframe non scaricabile: {timeframe}")
        self.limiter.acquire()
        try:
            response = self.client.get(
                f"{BASE_URL}/time_series",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_date": end.strftime("%Y-%m-%d %H:%M:%S"),
                    "timezone": "UTC",
                    "outputsize": PAGE_SIZE,
                    "order": "ASC",
                    "apikey": self._api_key,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            # Il messaggio di httpx contiene l'URL con la chiave: non va propagato.
            raise SourceError(f"twelvedata {symbol} {timeframe}: errore di rete") from None
        return parse_time_series(payload, symbol)


def parse_time_series(payload: object, symbol: str) -> pd.DataFrame:
    if not isinstance(payload, dict):
        raise SourceError(f"twelvedata {symbol}: risposta inattesa")
    if payload.get("status") == "error":
        code = payload.get("code")
        raise SourceError(f"twelvedata {symbol}: errore {code}")
    values = payload.get("values") or []
    if not values:
        return empty_ohlcv()
    frame = pd.DataFrame(values)
    if "volume" not in frame:
        frame["volume"] = 0.0
    frame["ts"] = pd.to_datetime(frame["datetime"], utc=True)
    return normalize_ohlcv(frame.set_index("ts"))
