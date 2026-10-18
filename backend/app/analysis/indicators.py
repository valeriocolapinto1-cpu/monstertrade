"""Indicatori tecnici calcolati solo con dati passati (nessun lookahead).

Ogni funzione restituisce valori allineati all'indice di ingresso: il valore alla
candela t usa solo le candele fino a t. Le medie di Wilder (RSI, ATR, ADX) partono
dalla media semplice dei primi n valori, come nella definizione originale.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).mean()


def ema(series: pd.Series, n: int) -> pd.Series:
    values = series.to_numpy(dtype="float64")
    out = np.full(len(values), np.nan)
    valid = np.flatnonzero(~np.isnan(values))
    if len(valid) < n:
        return pd.Series(out, index=series.index)
    start = valid[0] + n - 1
    alpha = 2 / (n + 1)
    out[start] = values[valid[0] : start + 1].mean()
    for i in range(start + 1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return pd.Series(out, index=series.index)


def rma(series: pd.Series, n: int) -> pd.Series:
    """Media mobile di Wilder: seme = media semplice dei primi n valori validi."""
    values = series.to_numpy(dtype="float64")
    out = np.full(len(values), np.nan)
    valid = np.flatnonzero(~np.isnan(values))
    if len(valid) < n:
        return pd.Series(out, index=series.index)
    start = valid[0] + n - 1
    out[start] = values[valid[0] : start + 1].mean()
    for i in range(start + 1, len(values)):
        out[i] = (out[i - 1] * (n - 1) + values[i]) / n
    return pd.Series(out, index=series.index)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = rma(delta.clip(lower=0), n)
    loss = rma((-delta).clip(lower=0), n)
    rs = gain / loss
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0).where(gain.notna())


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    ranges = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1
    )
    tr = ranges.max(axis=1)
    tr.iloc[0] = df["high"].iloc[0] - df["low"].iloc[0]
    return tr


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return rma(true_range(df), n)


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    plus_dm.iloc[0] = np.nan
    minus_dm.iloc[0] = np.nan
    tr = true_range(df)
    tr.iloc[0] = np.nan
    atr_n = rma(tr, n)
    plus_di = 100 * rma(plus_dm, n) / atr_n
    minus_di = 100 * rma(minus_dm, n) / atr_n
    total = plus_di + minus_di
    dx = (100 * (plus_di - minus_di).abs() / total).where(total != 0, 0.0)
    return pd.DataFrame({"adx": rma(dx, n), "plus_di": plus_di, "minus_di": minus_di})


def stochastic(df: pd.DataFrame, n: int = 14, smooth: int = 3, d: int = 3) -> pd.DataFrame:
    low = df["low"].rolling(n, min_periods=n).min()
    high = df["high"].rolling(n, min_periods=n).max()
    span = high - low
    raw = (100 * (df["close"] - low) / span).where(span != 0, 50.0).where(low.notna())
    k = sma(raw, smooth)
    return pd.DataFrame({"stoch_k": k, "stoch_d": sma(k, d)})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    std = close.rolling(n, min_periods=n).std(ddof=0)
    upper, lower = mid + k * std, mid - k * std
    width = upper - lower
    return pd.DataFrame(
        {
            "bb_mid": mid,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_pctb": ((close - lower) / width).where(width != 0),
            "bb_width": (width / mid).where(mid != 0),
        }
    )


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff().fillna(0.0))
    return pd.Series((direction * df["volume"]).cumsum(), index=df.index)


def vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP intraday che riparte a ogni giornata (UTC). NaN se mancano i volumi."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    day = pd.DatetimeIndex(df.index).normalize()
    pv = (typical * df["volume"]).groupby(day).cumsum()
    vol = df["volume"].groupby(day).cumsum()
    return (pv / vol).where(vol > 0)


def drawdown(close: pd.Series) -> pd.Series:
    return close / close.cummax() - 1


def max_drawdown(close: pd.Series) -> float:
    if close.empty:
        return float("nan")
    return float(drawdown(close).min())


def sharpe(returns: pd.Series, periods_per_year: float, risk_free: float = 0.0) -> float:
    """Sharpe annualizzato; `risk_free` è un tasso annuo."""
    excess = returns.dropna() - risk_free / periods_per_year
    std = excess.std(ddof=1)
    if len(excess) < 2 or not std or np.isnan(std):
        return float("nan")
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def realized_volatility(close: pd.Series, n: int = 20, periods_per_year: float = 252) -> pd.Series:
    log_ret = pd.Series(np.log(close / close.shift(1)), index=close.index)
    vol = log_ret.rolling(n, min_periods=n).std(ddof=1) * np.sqrt(periods_per_year)
    return pd.Series(vol, index=close.index)


def leverage_decay(sigma_annual: pd.Series | float, leverage: float) -> pd.Series | float:
    """Perdita annua attesa in un mercato laterale: (L^2 - L) / 2 * sigma^2.

    Approssimazione continua del decadimento da volatilità di un prodotto a leva con
    ribilanciamento giornaliero; vale 0 senza leva, ed è più forte per gli short
    (L = -3: 6 sigma^2, L = 3: 3 sigma^2).
    """
    return (leverage**2 - leverage) / 2 * sigma_annual**2


def correlation_matrix(closes: pd.DataFrame, window: int = 90) -> pd.DataFrame:
    """Correlazione dei rendimenti giornalieri sulle ultime `window` osservazioni comuni."""
    returns = closes.pct_change().dropna(how="all").tail(window)
    return returns.corr(min_periods=max(20, window // 3))


@dataclass(frozen=True)
class Level:
    price: float
    touches: int
    kind: str  # "supporto" o "resistenza"


def pivots(df: pd.DataFrame, window: int = 5) -> tuple[pd.Series, pd.Series]:
    """Massimi e minimi locali confermati: noti solo `window` candele dopo."""
    span = 2 * window + 1
    highs = df["high"][df["high"] == df["high"].rolling(span, center=True).max()]
    lows = df["low"][df["low"] == df["low"].rolling(span, center=True).min()]
    return highs, lows


def support_resistance(
    df: pd.DataFrame, lookback: int = 250, window: int = 5, max_levels: int = 3
) -> list[Level]:
    """Livelli con regole fisse: pivot raggruppati entro 0,5 ATR, i più toccati vicino al prezzo."""
    data = df.tail(lookback)
    if len(data) < 3 * window:
        return []
    highs, lows = pivots(data, window)
    points = np.sort(np.concatenate([highs.to_numpy(), lows.to_numpy()]))
    if len(points) == 0:
        return []
    tolerance = float(atr(data).iloc[-1]) * 0.5 if len(data) > 14 else 0.0
    clusters: list[list[float]] = [[points[0]]]
    for p in points[1:]:
        if p - np.mean(clusters[-1]) <= tolerance:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    last = float(data["close"].iloc[-1])
    levels = [
        Level(float(np.mean(c)), len(c), "supporto" if np.mean(c) < last else "resistenza")
        for c in clusters
    ]
    below = sorted((lv for lv in levels if lv.kind == "supporto"), key=lambda lv: -lv.price)
    above = sorted((lv for lv in levels if lv.kind == "resistenza"), key=lambda lv: lv.price)
    return below[:max_levels] + above[:max_levels]


FIB_RATIOS = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)


def fibonacci(df: pd.DataFrame, lookback: int = 120) -> dict[str, float] | None:
    """Ritracciamenti dell'ultimo movimento: massimo e minimo delle ultime `lookback` candele."""
    data = df.tail(lookback)
    if len(data) < 10:
        return None
    hi_t = data.index.get_loc(data["high"].idxmax())
    lo_t = data.index.get_loc(data["low"].idxmin())
    hi, lo = float(data["high"].max()), float(data["low"].min())
    if hi == lo:
        return None
    rising = int(lo_t) < int(hi_t)  # type: ignore[arg-type]  # movimento rialzista: si misura il ritracciamento dal massimo
    return {
        f"{r * 100:.1f}": (hi - (hi - lo) * r) if rising else (lo + (hi - lo) * r)
        for r in FIB_RATIOS
    }
