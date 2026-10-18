"""Calcolo di tutti gli indicatori del piano su una serie OHLCV."""

import numpy as np
import pandas as pd

from app.analysis import indicators as ind
from app.data.models import Timeframe
from app.data.universe import Calendar

# Candele per anno, per annualizzare volatilità e Sharpe.
_SESSION_MINUTES = {Calendar.NYSE: 390, Calendar.ALWAYS: 1440}
_DAYS = {Calendar.NYSE: 252, Calendar.ALWAYS: 365}


def periods_per_year(timeframe: Timeframe, calendar: Calendar) -> float:
    days = _DAYS[calendar]
    if timeframe is Timeframe.D1:
        return days
    if timeframe is Timeframe.W1:
        return 52
    return days * _SESSION_MINUTES[calendar] / timeframe.minutes


def compute_all(
    df: pd.DataFrame,
    timeframe: Timeframe,
    calendar: Calendar,
    leverage: float = 1.0,
    underlying_close: pd.Series | None = None,
) -> pd.DataFrame:
    """Tabella larga: una colonna per indicatore, stessa indice delle candele."""
    close = df["close"]
    out = pd.DataFrame(index=df.index)
    for n in (20, 50, 200):
        out[f"sma_{n}"] = ind.sma(close, n)
        out[f"ema_{n}"] = ind.ema(close, n)
    out = out.join(ind.macd(close))
    out = out.join(ind.adx(df))
    out["rsi_14"] = ind.rsi(close)
    out = out.join(ind.stochastic(df))
    out = out.join(ind.bollinger(close))
    out["atr_14"] = ind.atr(df)
    out["atr_pct"] = out["atr_14"] / close * 100
    has_volume = bool((df["volume"] > 0).any())
    out["obv"] = ind.obv(df) if has_volume else np.nan
    out["vwap"] = ind.vwap(df) if timeframe.intraday and has_volume else np.nan
    ppy = periods_per_year(timeframe, calendar)
    out["drawdown"] = ind.drawdown(close)
    # Per gli strumenti a leva la volatilità rilevante è quella del sottostante.
    base = underlying_close.reindex(df.index) if underlying_close is not None else close
    out["rvol_20"] = ind.realized_volatility(base, 20, ppy)
    if leverage != 1:
        out["decay_annual"] = ind.leverage_decay(out["rvol_20"], leverage)
    return out


def summary_metrics(df: pd.DataFrame, timeframe: Timeframe, calendar: Calendar) -> dict[str, float]:
    """Metriche di rischio sull'intera serie."""
    close = df["close"]
    ppy = periods_per_year(timeframe, calendar)
    returns = close.pct_change()
    years = len(close) / ppy if ppy else float("nan")
    total = float(close.iloc[-1] / close.iloc[0] - 1) if len(close) > 1 else float("nan")
    cagr = (1 + total) ** (1 / years) - 1 if years and years > 0 and total > -1 else float("nan")
    return {
        "max_drawdown": ind.max_drawdown(close),
        "sharpe": ind.sharpe(returns, ppy),
        "volatility": float(returns.std(ddof=1) * np.sqrt(ppy)),
        "cagr": float(cagr),
    }
