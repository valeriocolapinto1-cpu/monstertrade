from datetime import datetime

import pandas as pd
import yfinance as yf

from app.data.models import Timeframe, empty_ohlcv, normalize_ohlcv
from app.data.ratelimit import RateLimiter
from app.data.sources.base import SourceError

# Yahoo limita lo storico intraday: 5 e 15 minuti solo per gli ultimi 60 giorni.
INTRADAY_HISTORY = pd.Timedelta(days=59)


class YFinanceSource:
    """Riserva non ufficiale: può rompersi senza preavviso, va usata con parsimonia."""

    name = "yfinance"

    def __init__(self, limiter: RateLimiter | None = None) -> None:
        self.limiter = limiter or RateLimiter(capacity=1, per_seconds=2)

    def available(self) -> bool:
        return True

    def max_history(self, timeframe: Timeframe) -> pd.Timedelta | None:
        return INTRADAY_HISTORY if timeframe.intraday else None

    def fetch(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        if not timeframe.stored:
            raise ValueError(f"timeframe non scaricabile: {timeframe}")
        self.limiter.acquire()
        try:
            raw = yf.Ticker(symbol).history(
                start=start,
                end=end,
                interval=timeframe.value,
                auto_adjust=False,
                actions=False,
                raise_errors=True,
            )
        except Exception as exc:  # yfinance solleva eccezioni eterogenee
            raise SourceError(f"yfinance {symbol} {timeframe}: {exc}") from exc
        return parse_history(raw, timeframe)


def parse_history(raw: pd.DataFrame, timeframe: Timeframe) -> pd.DataFrame:
    if raw is None or raw.empty:
        return empty_ohlcv()
    frame = raw.rename(columns=str.lower)
    if "volume" not in frame:
        frame["volume"] = 0.0
    index = pd.DatetimeIndex(frame.index)
    if timeframe is Timeframe.D1:
        # Le giornaliere arrivano alla mezzanotte locale: si ancorano alla data UTC.
        index = pd.DatetimeIndex(index.tz_localize(None).normalize()).tz_localize("UTC")
    frame.index = index
    # Yahoo restituisce valori float32: si arrotonda per togliere il rumore di conversione.
    prices = ["open", "high", "low", "close"]
    frame[prices] = frame[prices].astype("float64").round(4)
    return normalize_ohlcv(frame)
