"""Backtest di strategie semplici con vectorbt.

Regole contro il lookahead: il segnale è calcolato sulla chiusura della candela t e
l'operazione avviene all'apertura della candela t+1. Commissioni e spread sono
applicati a ogni ingresso e uscita. Solo posizioni lunghe: l'esposizione ribassista
passa dagli ETF short, che hanno un proprio backtest.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import vectorbt as vbt

from app.analysis import indicators as ind
from app.analysis.compute import periods_per_year
from app.data.models import Timeframe
from app.data.universe import Calendar

Signal = Callable[[pd.DataFrame], pd.Series]


def sma_cross(fast: int, slow: int) -> Signal:
    return lambda df: ind.sma(df["close"], fast) > ind.sma(df["close"], slow)


def above_sma(n: int) -> Signal:
    return lambda df: df["close"] > ind.sma(df["close"], n)


def ema_cross(fast: int, slow: int) -> Signal:
    return lambda df: ind.ema(df["close"], fast) > ind.ema(df["close"], slow)


def momentum(n: int) -> Signal:
    """Momentum a serie temporale: in posizione se il rendimento su n candele è positivo."""
    return lambda df: df["close"].pct_change(n) > 0


def rsi_macd(df: pd.DataFrame) -> pd.Series:
    """Momentum di breve: RSI sopra 50 e istogramma MACD positivo."""
    return (ind.rsi(df["close"]) > 50) & (ind.macd(df["close"])["macd_hist"] > 0)


def buy_and_hold(df: pd.DataFrame) -> pd.Series:
    return pd.Series(True, index=df.index)


@dataclass(frozen=True)
class Strategy:
    key: str
    name: str
    family: str  # "trend", "momentum" o "riferimento"
    signal: Signal


HORIZONS: dict[str, tuple[Timeframe, list[Strategy]]] = {
    "day": (
        Timeframe.M15,
        [
            Strategy("ema_20_50", "Incrocio EMA 20/50", "trend", ema_cross(20, 50)),
            Strategy("rsi_macd", "RSI > 50 e MACD positivo", "momentum", rsi_macd),
            Strategy("buy_hold", "Compra e tieni", "riferimento", buy_and_hold),
        ],
    ),
    "swing": (
        Timeframe.D1,
        [
            Strategy("sma_50_200", "Incrocio SMA 50/200", "trend", sma_cross(50, 200)),
            Strategy("above_sma_200", "Prezzo sopra SMA 200", "trend", above_sma(200)),
            Strategy("mom_63", "Momentum 3 mesi", "momentum", momentum(63)),
            Strategy("buy_hold", "Compra e tieni", "riferimento", buy_and_hold),
        ],
    ),
    "long": (
        Timeframe.W1,
        [
            Strategy("above_sma_40w", "Prezzo sopra SMA 40 settimane", "trend", above_sma(40)),
            Strategy("mom_52w", "Momentum 12 mesi", "momentum", momentum(52)),
            Strategy("buy_hold", "Compra e tieni", "riferimento", buy_and_hold),
        ],
    ),
}


@dataclass
class Result:
    symbol: str
    horizon: str
    strategy: str
    strategy_name: str
    family: str
    start: str
    end: str
    bars: int
    total_return: float
    cagr: float
    sharpe: float
    max_drawdown: float
    trades: int
    win_rate: float
    exposure: float
    costs_paid: float
    first_half: float
    second_half: float

    def to_dict(self) -> dict[str, object]:
        return {
            k: (None if isinstance(v, float) and not np.isfinite(v) else v)
            for k, v in asdict(self).items()
        }


def positions(df: pd.DataFrame, signal: Signal, flat_at_session_end: bool) -> pd.Series:
    """Posizione desiderata alla chiusura di ogni candela (True = investito)."""
    raw = signal(df).fillna(False).astype(bool)
    if flat_at_session_end:
        day = pd.DatetimeIndex(df.index).normalize()
        last_of_day = pd.Series(day, index=df.index).shift(-1) != day
        raw = raw & ~last_of_day
    return raw


def run(
    df: pd.DataFrame,
    strategy: Strategy,
    per_side_cost: float,
    timeframe: Timeframe,
    calendar: Calendar,
    flat_at_session_end: bool = False,
) -> vbt.Portfolio:
    want = positions(df, strategy.signal, flat_at_session_end)
    # Esecuzione alla candela successiva: si sposta la posizione di una candela.
    held = want.shift(1, fill_value=False)
    entries = held & ~held.shift(1, fill_value=False)
    exits = ~held & held.shift(1, fill_value=False)
    freq = pd.Timedelta(minutes=timeframe.minutes)
    return vbt.Portfolio.from_signals(
        close=df["close"],
        entries=entries,
        exits=exits,
        price=df["open"],
        fees=per_side_cost,
        init_cash=10_000.0,
        freq=freq,
        direction="longonly",
    )


def _half_return(value: pd.Series, first: bool) -> float:
    mid = len(value) // 2
    part = value.iloc[: mid + 1] if first else value.iloc[mid:]
    return float(part.iloc[-1] / part.iloc[0] - 1) if len(part) > 1 else float("nan")


def evaluate(
    symbol: str,
    horizon: str,
    df: pd.DataFrame,
    strategy: Strategy,
    per_side_cost: float,
    timeframe: Timeframe,
    calendar: Calendar,
) -> Result:
    flat = horizon == "day" and calendar is Calendar.NYSE
    pf = run(df, strategy, per_side_cost, timeframe, calendar, flat_at_session_end=flat)
    value = pf.value()
    returns = value.pct_change().fillna(0.0)
    ppy = periods_per_year(timeframe, calendar)
    total = float(value.iloc[-1] / value.iloc[0] - 1)
    years = len(value) / ppy
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 and total > -1 else float("nan")
    trades = pf.trades
    count = int(trades.count())
    win = float(trades.win_rate()) if count else float("nan")
    held = pf.asset_value() > 0
    return Result(
        symbol=symbol,
        horizon=horizon,
        strategy=strategy.key,
        strategy_name=strategy.name,
        family=strategy.family,
        start=str(df.index[0].date()),
        end=str(df.index[-1].date()),
        bars=len(df),
        total_return=total,
        cagr=float(cagr),
        sharpe=ind.sharpe(returns, ppy),
        max_drawdown=ind.max_drawdown(value),
        trades=count,
        win_rate=win,
        exposure=float(held.mean()),
        costs_paid=float(pf.orders.fees.sum() / pf.init_cash),
        first_half=_half_return(value, True),
        second_half=_half_return(value, False),
    )
