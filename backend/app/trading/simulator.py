"""Simulazione (paper trading) sui prezzi reali, senza guardare il futuro.

- Ingresso all'apertura della prima candela successiva al segnale.
- Uscita allo stop o all'obiettivo quando il prezzo li tocca; se apre già oltre
  (gap) si esce all'apertura, a un prezzo peggiore. Se nella stessa candela sono
  toccati entrambi si assume lo stop (ipotesi prudente).
- Uscita a tempo dopo un numero massimo di candele (e a fine sessione nel day
  trading sugli strumenti USA).
- Costi per lato su ingresso e uscita.
"""

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

MAX_BARS = {"day": 26, "swing": 20, "long": 26}


@dataclass(frozen=True)
class Entry:
    ts: datetime
    price: float


@dataclass(frozen=True)
class Exit:
    ts: datetime
    price: float
    reason: str  # "stop", "obiettivo", "tempo", "segnale"


def find_entry(bars: pd.DataFrame, signal_ts: datetime) -> Entry | None:
    after = bars[bars.index > pd.Timestamp(signal_ts)]
    if after.empty:
        return None
    return Entry(after.index[0].to_pydatetime(), float(after["open"].iloc[0]))


def find_exit(
    bars: pd.DataFrame,
    entry: Entry,
    stop: float,
    target: float,
    max_bars: int,
    flat_at_session_end: bool = False,
) -> Exit | None:
    held = bars[bars.index >= pd.Timestamp(entry.ts)]
    days = pd.DatetimeIndex(held.index).normalize()
    stamps = pd.DatetimeIndex(held.index)
    for i, (_, bar) in enumerate(held.iterrows()):
        when = stamps[i].to_pydatetime()
        o, h, low, c = (float(bar[k]) for k in ("open", "high", "low", "close"))
        if i > 0 and o <= stop:
            return Exit(when, o, "stop")
        if low <= stop:
            return Exit(when, stop, "stop")
        if i > 0 and o >= target:
            return Exit(when, o, "obiettivo")
        if h >= target:
            return Exit(when, target, "obiettivo")
        last_of_session = i + 1 < len(held) and days[i + 1] != days[i]
        if i + 1 >= max_bars or (flat_at_session_end and last_of_session):
            return Exit(when, c, "tempo")
    return None


def pnl(
    size_eur: float, entry_price: float, exit_price: float, per_side: float
) -> tuple[float, float]:
    """Risultato netto e costi in euro."""
    exit_value = size_eur * exit_price / entry_price
    fees = size_eur * per_side + exit_value * per_side
    return exit_value - size_eur - fees, fees
