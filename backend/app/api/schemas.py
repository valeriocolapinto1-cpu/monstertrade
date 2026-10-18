from datetime import datetime

from pydantic import BaseModel


class Instrument(BaseModel):
    symbol: str
    name: str
    kind: str
    currency: str
    leverage: float
    underlying: str | None
    reference_ticker: str | None
    synthetic: bool
    last_price: float | None
    change_pct: float | None
    last_ts: datetime | None


class Candle(BaseModel):
    time: int  # secondi Unix, inizio della candela
    open: float
    high: float
    low: float
    close: float
    volume: float


class Candles(BaseModel):
    symbol: str
    timeframe: str
    source: str | None
    candles: list[Candle]


class QualityItem(BaseModel):
    symbol: str
    timeframe: str
    rows: int
    first: str | None
    last: str | None
    missing: int
    missing_sample: list[str]
    duplicates: int
    invalid: int
    outliers: list[str]
    complete: bool


class Quality(BaseModel):
    generated_at: datetime
    complete: bool
    items: list[QualityItem]
