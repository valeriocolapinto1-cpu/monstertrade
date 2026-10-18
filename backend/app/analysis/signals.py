"""Motore dei segnali: score da -100 a +100 per strumento e orizzonte.

Lo score combina quattro componenti (trend, momentum, volumi, sentiment), ognuna media
di segnali elementari in [-1, 1]. I pesi iniziali sono semplici e regolabili; se una
componente non è disponibile (ad esempio volumi assenti sugli indici) il suo peso si
ridistribuisce sulle altre. Ogni segnale elementare viene salvato, così la proposta
mostra sia i segnali favorevoli sia quelli contrari.

Per gli strumenti a leva il segnale si calcola sul sottostante: lo score ha lo stesso
segno per i long e segno opposto per gli short; il fattore di leva entra nel rischio.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.analysis import indicators as ind
from app.analysis.compute import compute_all
from app.data.models import Timeframe
from app.data.universe import Calendar

Horizon = str  # "day", "swing", "long"

HORIZON_TIMEFRAME: dict[Horizon, Timeframe] = {
    "day": Timeframe.M15,
    "swing": Timeframe.D1,
    "long": Timeframe.W1,
}

# Pesi iniziali del piano (trend / momentum / volumi / sentiment).
INITIAL_WEIGHTS: dict[Horizon, dict[str, float]] = {
    "day": {"trend": 0.40, "momentum": 0.35, "volume": 0.15, "sentiment": 0.10},
    "swing": {"trend": 0.40, "momentum": 0.30, "volume": 0.15, "sentiment": 0.15},
    "long": {"trend": 0.50, "momentum": 0.30, "volume": 0.10, "sentiment": 0.10},
}

# Pesi adottati dopo il backtest (docs/sentiment-score.md): con i pesi iniziali lo score
# non batteva le strategie semplici, perché momentum e volumi cambiano spesso segno e
# moltiplicano le operazioni. Tra cinque varianti fissate in anticipo è stata scelta la
# migliore sulla prima metà dello storico e verificata sulla seconda. Momentum e volumi
# restano tra i segnali favorevoli e contrari mostrati, ma non spostano lo score.
WEIGHTS: dict[Horizon, dict[str, float]] = {
    h: {"trend": 0.80, "momentum": 0.0, "volume": 0.0, "sentiment": 0.20}
    for h in ("day", "swing", "long")
}

# Isteresi: si entra sopra ENTER_SCORE e si esce sotto EXIT_SCORE (meno operazioni).
ENTER_SCORE = 20.0
EXIT_SCORE = 0.0

# Giorni di sentiment considerati per orizzonte.
SENTIMENT_DAYS: dict[Horizon, int] = {"day": 1, "swing": 3, "long": 14}

# Parametri per orizzonte: medie lente/veloci e finestra del momentum.
PARAMS: dict[Horizon, dict[str, object]] = {
    "day": {"fast": "ema_20", "slow": "ema_50", "anchor": "ema_200", "roc": 20},
    "swing": {"fast": "sma_50", "slow": "sma_200", "anchor": "sma_200", "roc": 63},
    "long": {"fast": "sma_20", "slow": "sma_50", "anchor": "sma_50", "roc": 52},
}


@dataclass(frozen=True)
class SignalDef:
    key: str
    component: str
    label_pos: str
    label_neg: str


SIGNALS: tuple[SignalDef, ...] = (
    SignalDef(
        "price_anchor", "trend", "Prezzo sopra la media lenta", "Prezzo sotto la media lenta"
    ),
    SignalDef("ma_cross", "trend", "Media veloce sopra la lenta", "Media veloce sotto la lenta"),
    SignalDef("macd", "trend", "Istogramma MACD positivo", "Istogramma MACD negativo"),
    SignalDef("adx_di", "trend", "Trend con +DI prevalente", "Trend con -DI prevalente"),
    SignalDef("rsi", "momentum", "RSI sopra 50", "RSI sotto 50"),
    SignalDef(
        "rsi_extreme",
        "momentum",
        "RSI in ipervenduto: possibile rimbalzo",
        "RSI in ipercomprato: rischio di ritracciamento",
    ),
    SignalDef("stoch", "momentum", "Stocastico in salita", "Stocastico in discesa"),
    SignalDef("roc", "momentum", "Rendimento recente positivo", "Rendimento recente negativo"),
    SignalDef("obv", "volume", "Volumi che confermano il movimento", "Volumi in divergenza"),
    SignalDef("vwap", "volume", "Prezzo sopra il VWAP", "Prezzo sotto il VWAP"),
    SignalDef("sentiment", "sentiment", "Sentiment positivo", "Sentiment negativo"),
    SignalDef(
        "sentiment_extreme",
        "sentiment",
        "Paura estrema: spesso vicina ai minimi",
        "Euforia estrema: spesso vicina ai massimi",
    ),
)
BY_KEY = {s.key: s for s in SIGNALS}


def _clip(x: pd.Series) -> pd.Series:
    return x.clip(-1.0, 1.0)


def elementary_signals(
    df: pd.DataFrame,
    horizon: Horizon,
    calendar: Calendar,
    sentiment: pd.Series | None = None,
) -> pd.DataFrame:
    """Tabella dei segnali elementari in [-1, 1] (NaN = non disponibile)."""
    tf = HORIZON_TIMEFRAME[horizon]
    p = PARAMS[horizon]
    w = compute_all(df, tf, calendar)
    close = df["close"]
    atr = w["atr_14"]
    out = pd.DataFrame(index=df.index)
    anchor = w[str(p["anchor"])]
    out["price_anchor"] = _clip((close / anchor - 1) / 0.05)
    fast, slow = w[str(p["fast"])], w[str(p["slow"])]
    out["ma_cross"] = _clip((fast / slow - 1) / 0.03)
    out["macd"] = _clip(w["macd_hist"] / (0.5 * atr))
    di_sum = w["plus_di"] + w["minus_di"]
    strength = (w["adx"] / 25).clip(0, 1.5) / 1.5
    out["adx_di"] = _clip((w["plus_di"] - w["minus_di"]) / di_sum * strength * 2)
    out["rsi"] = _clip((w["rsi_14"] - 50) / 20)
    rsi = w["rsi_14"]
    out["rsi_extreme"] = np.where(rsi > 75, -0.6, np.where(rsi < 25, 0.6, 0.0))
    out.loc[rsi.isna(), "rsi_extreme"] = np.nan
    out["stoch"] = _clip((w["stoch_k"] - w["stoch_d"]) / 10 + (w["stoch_k"] - 50) / 100)
    n = int(str(p["roc"]))
    roc = close.pct_change(n)
    vol = ind.realized_volatility(close, n, 1.0) * np.sqrt(n)
    out["roc"] = _clip(roc / (2 * vol))
    if w["obv"].notna().any():
        obv_slope = w["obv"].diff(10)
        price_slope = close.diff(10)
        aligned = np.sign(obv_slope) == np.sign(price_slope)
        out["obv"] = np.where(aligned, np.sign(price_slope) * 0.5, -np.sign(price_slope) * 0.5)
        out.loc[obv_slope.isna() | price_slope.isna(), "obv"] = np.nan
    else:
        out["obv"] = np.nan
    out["vwap"] = _clip((close / w["vwap"] - 1) / 0.005) if horizon == "day" else np.nan
    if sentiment is not None and not sentiment.empty:
        s = align_sentiment(sentiment, df.index, SENTIMENT_DAYS[horizon])
        out["sentiment"] = _clip(s * 2)
        out["sentiment_extreme"] = np.where(s > 0.5, -0.5, np.where(s < -0.5, 0.5, 0.0))
        out.loc[s.isna(), "sentiment_extreme"] = np.nan
    else:
        out["sentiment"] = np.nan
        out["sentiment_extreme"] = np.nan
    return out


def align_sentiment(daily: pd.Series, index: pd.Index, days: int) -> pd.Series:
    """Media del sentiment dei `days` giorni conclusi prima della candela (niente lookahead)."""
    series = daily.sort_index()
    series.index = pd.DatetimeIndex(series.index).tz_localize(None).normalize()
    rolled = series.rolling(f"{days}D").mean()
    # Il sentiment di un giorno è noto solo a giornata conclusa: si sposta di un giorno.
    rolled.index = rolled.index + pd.Timedelta(days=1)
    bars = pd.DatetimeIndex(index).tz_convert(None)
    pos = np.searchsorted(rolled.index.values, bars.values, side="right") - 1
    values = np.where(pos >= 0, rolled.to_numpy()[np.clip(pos, 0, None)], np.nan)
    # Oltre una settimana senza dati il sentiment non è più attuale.
    age = np.where(pos >= 0, (bars.values - rolled.index.values[np.clip(pos, 0, None)]), 0)
    stale = age > np.timedelta64(7 + days, "D")
    return pd.Series(np.where(stale, np.nan, values), index=index)


def combine(
    signals: pd.DataFrame, horizon: Horizon, weights: dict[str, float] | None = None
) -> pd.DataFrame:
    """Componenti e score finale per ogni candela."""
    weights = weights or WEIGHTS[horizon]
    comps = pd.DataFrame(index=signals.index)
    for comp in weights:
        cols = [s.key for s in SIGNALS if s.component == comp and s.key in signals]
        comps[comp] = signals[cols].mean(axis=1, skipna=True) if cols else np.nan
    w = pd.DataFrame(
        {c: np.where(comps[c].notna(), weights[c], 0.0) for c in weights}, index=comps.index
    )
    total = w.sum(axis=1)
    score = (comps.fillna(0.0) * w).sum(axis=1) / total.replace(0, np.nan) * 100
    comps["score"] = score.clip(-100, 100)
    return comps


@dataclass
class Snapshot:
    score: float
    components: dict[str, float | None]
    favorable: list[dict[str, object]] = field(default_factory=list)
    contrary: list[dict[str, object]] = field(default_factory=list)


def snapshot(signals_row: pd.Series, comps_row: pd.Series, direction: float = 1.0) -> Snapshot:
    """Fotografia leggibile dell'ultima candela; `direction` = -1 per gli strumenti short.

    Le etichette descrivono il sottostante (es. "Prezzo sopra la media lenta" del Nasdaq),
    il valore ha già il segno dello strumento.
    """
    score = float(comps_row["score"]) * direction
    snap = Snapshot(
        score=round(score, 1),
        components={
            str(k): (None if pd.isna(v) else round(float(v) * direction, 3))
            for k, v in comps_row.items()
            if k != "score"
        },
    )
    # Favorevole = a favore dell'acquisto dello strumento (per gli short: segnale del
    # sottostante invertito), indipendentemente dal segno dello score.
    for key, raw in signals_row.items():
        if pd.isna(raw) or abs(float(raw)) < 0.1:
            continue
        value = float(raw)
        definition = BY_KEY[str(key)]
        label = definition.label_pos if value > 0 else definition.label_neg
        entry = {
            "key": key,
            "component": definition.component,
            "label": label,
            "value": round(value * direction, 2),
        }
        (snap.favorable if value * direction > 0 else snap.contrary).append(entry)

    def order(entry: dict[str, object]) -> float:
        return -abs(float(str(entry["value"])))

    snap.favorable.sort(key=order)
    snap.contrary.sort(key=order)
    return snap


def hysteresis(
    score: pd.Series, enter: float = ENTER_SCORE, exit_: float = EXIT_SCORE
) -> pd.Series:
    """Posizione desiderata: entra sopra `enter`, resta finché lo score non scende sotto `exit_`."""
    held = False
    out = np.zeros(len(score), dtype=bool)
    for i, value in enumerate(score.to_numpy(dtype="float64")):
        if np.isnan(value):
            held = False
        elif not held and value > enter:
            held = True
        elif held and value < exit_:
            held = False
        out[i] = held
    return pd.Series(out, index=score.index)
