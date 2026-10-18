"""Score storico di uno strumento: segnali del sottostante, direzione della leva."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import Connection

from app.analysis import indicators as ind
from app.analysis.signals import HORIZON_TIMEFRAME, combine, elementary_signals
from app.data.models import Timeframe, resample_weekly
from app.data.universe import BY_SYMBOL, InstrumentSpec
from app.db import repository as repo


@dataclass
class ScoreFrame:
    spec: InstrumentSpec
    horizon: str
    prices: pd.DataFrame  # prezzi dello strumento (sintetici per la leva)
    signals: pd.DataFrame  # segnali elementari del sottostante
    components: pd.DataFrame  # componenti e score del sottostante
    direction: float

    @property
    def score(self) -> pd.Series:
        return self.components["score"] * self.direction


def load_frame(
    conn: Connection, symbol: str, timeframe: Timeframe, limit: int | None
) -> pd.DataFrame:
    ids = repo.instrument_ids(conn)
    if symbol not in ids:
        return pd.DataFrame()
    if timeframe is Timeframe.W1:
        daily = repo.load_prices(conn, ids[symbol], Timeframe.D1)
        weekly = resample_weekly(daily)
        return weekly.tail(limit) if limit else weekly
    return repo.load_prices(conn, ids[symbol], timeframe, limit=limit)


def build(
    conn: Connection, spec: InstrumentSpec, horizon: str, limit: int | None = None
) -> ScoreFrame | None:
    tf = HORIZON_TIMEFRAME[horizon]
    base = BY_SYMBOL[spec.underlying] if spec.underlying else spec
    under = load_frame(conn, base.symbol, tf, limit)
    own = load_frame(conn, spec.symbol, tf, limit)
    if under.empty or own.empty:
        return None
    ids = repo.instrument_ids(conn)
    sentiment = repo.daily_sentiment_index(repo.load_sentiment(conn, ids[base.symbol]))
    sig = elementary_signals(under, horizon, base.calendar, sentiment)
    comps = combine(sig, horizon)
    common = own.index.intersection(comps.index)
    return ScoreFrame(
        spec,
        horizon,
        own.loc[common],
        sig.loc[common],
        comps.loc[common],
        float(np.sign(spec.leverage)),
    )


def atr_context(prices: pd.DataFrame, lookback: int = 252) -> tuple[float, float]:
    """ATR % attuale e mediana dell'ATR % nell'ultimo anno di candele."""
    atr_pct = (ind.atr(prices) / prices["close"] * 100).dropna()
    if atr_pct.empty:
        return float("nan"), float("nan")
    return float(atr_pct.iloc[-1]), float(atr_pct.tail(lookback).median())
