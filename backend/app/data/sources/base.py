from datetime import datetime
from typing import Protocol

import pandas as pd

from app.data.models import Timeframe


class SourceError(Exception):
    """Errore della fonte (rete, limiti, formato): si passa alla riserva."""


class SourceUnavailableError(SourceError):
    """Fonte non configurata (ad esempio chiave API mancante)."""


class PriceSource(Protocol):
    name: str

    def available(self) -> bool: ...

    def max_history(self, timeframe: Timeframe) -> pd.Timedelta | None:
        """Profondità massima di storico ottenibile, None se illimitata."""
        ...

    def fetch(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Candele OHLCV normalizzate (indice UTC = inizio della candela) in [start, end)."""
        ...
