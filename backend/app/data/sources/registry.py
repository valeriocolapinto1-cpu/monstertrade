from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import pandas as pd

from app.config import Settings
from app.data.cache import FrameCache
from app.data.models import Timeframe
from app.data.sources.base import PriceSource, SourceError
from app.data.sources.binance import BinanceSource
from app.data.sources.twelvedata import TwelveDataSource
from app.data.sources.yfinance_source import YFinanceSource
from app.data.universe import InstrumentSpec

RECENT_TTL = 30 * 60
HISTORICAL_TTL = 30 * 86_400


@dataclass
class FetchResult:
    frame: pd.DataFrame
    source: str
    errors: list[str]


class SourceRegistry:
    """Fonti sostituibili: si prova la principale, poi le riserve, con cache su disco."""

    def __init__(self, sources: dict[str, PriceSource], cache: FrameCache | None) -> None:
        self.sources = sources
        self.cache = cache

    @classmethod
    def from_settings(cls, settings: Settings, client: httpx.Client) -> "SourceRegistry":
        key = settings.twelve_data_api_key
        sources: dict[str, PriceSource] = {
            "twelvedata": TwelveDataSource(client, key.get_secret_value() if key else None),
            "binance": BinanceSource(client),
            "yfinance": YFinanceSource(),
        }
        return cls(sources, FrameCache(settings.cache_dir))

    def fetch(
        self,
        spec: InstrumentSpec,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        now: datetime | None = None,
    ) -> FetchResult:
        now = now or datetime.now(UTC)
        errors: list[str] = []
        for ref in spec.sources:
            source = self.sources.get(ref.source)
            if source is None or not source.available():
                continue
            begin = start
            limit = source.max_history(timeframe)
            if limit is not None:
                begin = max(start, now - limit.to_pytimedelta())
            if begin >= end:
                continue
            key = f"{ref.source}|{ref.symbol}|{timeframe}|{begin:%Y%m%d%H}|{end:%Y%m%d%H}"
            recent = end > now - pd.Timedelta(days=2).to_pytimedelta()
            ttl = RECENT_TTL if recent else HISTORICAL_TTL
            frame = self.cache.get(key, ttl) if self.cache else None
            if frame is None:
                try:
                    frame = source.fetch(ref.symbol, timeframe, begin, end)
                except SourceError as exc:
                    errors.append(str(exc))
                    continue
                if self.cache is not None and not frame.empty:
                    self.cache.set(key, frame)
            if not frame.empty:
                return FetchResult(frame, ref.source, errors)
            errors.append(f"{ref.source} {ref.symbol} {timeframe}: nessun dato")
        return FetchResult(pd.DataFrame(), "", errors)
