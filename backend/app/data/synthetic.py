"""Serie sintetiche degli strumenti a leva ricavate dal sottostante.

Modello con ribilanciamento giornaliero (come gli ETP a leva reali):

    r_strumento = L * r_sottostante + (1 - L) * r_finanziamento - TER

dove i costi maturano sui giorni di calendario trascorsi. Per L = 3 il termine
(1 - L) = -2 è il costo del denaro preso a prestito; per L = -3 vale +4, cioè gli
interessi sulla liquidità a garanzia. È un'approssimazione: non include spread dello
swap, tracking error, cambio valuta e orari diversi della borsa di quotazione.
"""

import numpy as np
import pandas as pd

from app.data.models import OHLCV_COLUMNS, empty_ohlcv

BASE_LEVEL = 100.0
DAYS_PER_YEAR = 365.0
# Data fissa in cui la serie vale 100: livelli leggibili oggi e stabili nel tempo
# (le operazioni salvate restano confrontabili). Gli short decadono molto su 25 anni.
ANCHOR = pd.Timestamp("2025-01-02", tz="UTC")


def daily_costs(index: pd.DatetimeIndex, leverage: float, ter: float, funding: float) -> pd.Series:
    """Rendimento di costo/finanziamento per ogni candela giornaliera (prima = 0)."""
    days = pd.Series(index, index=index).diff().dt.total_seconds().fillna(0) / 86_400
    return days / DAYS_PER_YEAR * ((1 - leverage) * funding - ter)


def _map_extremes(
    ref_level: pd.Series, ref_under: pd.Series, under: pd.DataFrame, leverage: float
) -> pd.DataFrame:
    def lev(col: str) -> pd.Series:
        # Come nel giornaliero, lo strumento non può scendere sotto zero.
        factor = (1 + leverage * (under[col] / ref_under - 1)).clip(lower=1e-6)
        return ref_level * factor

    high, low = (lev("high"), lev("low")) if leverage >= 0 else (lev("low"), lev("high"))
    out = pd.DataFrame(
        {"open": lev("open"), "high": high, "low": low, "close": lev("close")}, index=under.index
    )
    out["high"] = out[["open", "high", "low", "close"]].max(axis=1)
    out["low"] = out[["open", "high", "low", "close"]].min(axis=1)
    out["volume"] = 0.0
    return out[OHLCV_COLUMNS]


def synthesize_daily(
    under: pd.DataFrame, leverage: float, ter: float, funding: float
) -> pd.DataFrame:
    if under.empty:
        return empty_ohlcv()
    returns = under["close"].pct_change().fillna(0.0)
    costs = daily_costs(pd.DatetimeIndex(under.index), leverage, ter, funding)
    growth = 1 + leverage * returns + costs
    # Un fattore <= 0 azzererebbe lo strumento (rischio reale dei 3x): si limita a quasi zero.
    growth = growth.clip(lower=1e-6)
    close = BASE_LEVEL * growth.cumprod()
    anchored = close[close.index >= ANCHOR]
    if not anchored.empty:
        close = close * (BASE_LEVEL / anchored.iloc[0])
    prev_close = close.shift(1).fillna(close.iloc[0])
    prev_under = under["close"].shift(1).fillna(under["close"].iloc[0])
    out = _map_extremes(prev_close, prev_under, under, leverage)
    out["close"] = close
    out["high"] = out[["open", "high", "low", "close"]].max(axis=1)
    out["low"] = out[["open", "high", "low", "close"]].min(axis=1)
    return out


def synthesize_intraday(
    under_intraday: pd.DataFrame,
    under_daily: pd.DataFrame,
    synth_daily: pd.DataFrame,
    leverage: float,
) -> pd.DataFrame:
    """Intraday con reset alla chiusura della sessione precedente.

    Ogni candela usa come riferimento la chiusura giornaliera precedente (del
    sottostante e della serie sintetica), quindi l'intraday è coerente con il
    giornaliero. Le candele senza giornaliera precedente vengono scartate.
    """
    if under_intraday.empty or under_daily.empty:
        return empty_ohlcv()
    session = pd.DatetimeIndex(under_intraday.index).normalize()
    daily_dates = pd.DatetimeIndex(under_daily.index)
    # Posizione della sessione precedente rispetto alla data della candela.
    pos = np.searchsorted(daily_dates.values, session.values, side="left") - 1
    valid = pos >= 0
    under = under_intraday[valid]
    pos = pos[valid]
    ref_under = pd.Series(under_daily["close"].to_numpy()[pos], index=under.index)
    ref_level = pd.Series(
        synth_daily["close"].reindex(daily_dates).to_numpy()[pos], index=under.index
    )
    return _map_extremes(ref_level, ref_under, under, leverage).dropna()
