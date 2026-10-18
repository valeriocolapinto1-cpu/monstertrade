from enum import StrEnum

import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class Timeframe(StrEnum):
    M5 = "5m"
    M15 = "15m"
    D1 = "1d"
    W1 = "1w"

    @property
    def stored(self) -> bool:
        """Il settimanale si ricava dal giornaliero, non si salva."""
        return self is not Timeframe.W1

    @property
    def intraday(self) -> bool:
        return self in (Timeframe.M5, Timeframe.M15)

    @property
    def minutes(self) -> int:
        return {"5m": 5, "15m": 15, "1d": 1440, "1w": 10080}[self.value]


def empty_ohlcv() -> pd.DataFrame:
    frame = pd.DataFrame(columns=OHLCV_COLUMNS, dtype="float64")
    frame.index = pd.DatetimeIndex([], tz="UTC", name="ts")
    return frame


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """Indice UTC ordinato e senza duplicati, colonne float in ordine standard."""
    if frame.empty:
        return empty_ohlcv()
    out = frame[OHLCV_COLUMNS].astype("float64")
    index = pd.DatetimeIndex(out.index)
    index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    out.index = index.rename("ts")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def resample_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Candele settimanali (settimana che inizia il lunedì) dalle giornaliere."""
    if daily.empty:
        return empty_ohlcv()
    weekly = daily.resample("W-MON", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return weekly.dropna(subset=["close"])
