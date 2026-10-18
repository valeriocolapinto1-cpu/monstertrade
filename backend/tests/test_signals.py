import numpy as np
import pandas as pd
import pytest

from app.analysis.signals import (
    SIGNALS,
    align_sentiment,
    combine,
    elementary_signals,
    snapshot,
)
from app.data.universe import Calendar


def trending(n: int = 400, drift: float = 0.002, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame(
        {"open": close, "high": close * 1.005, "low": close * 0.995, "close": close, "volume": 0.0},
        index=idx,
    )


def test_uptrend_scores_positive_and_downtrend_negative() -> None:
    up = combine(elementary_signals(trending(drift=0.003), "swing", Calendar.ALWAYS), "swing")
    down = combine(elementary_signals(trending(drift=-0.003), "swing", Calendar.ALWAYS), "swing")
    assert up["score"].iloc[-1] > 30
    assert down["score"].iloc[-1] < -30
    assert up["score"].between(-100, 100).all() or up["score"].isna().any()


def test_missing_components_redistribute_weight() -> None:
    sig = pd.DataFrame({s.key: np.nan for s in SIGNALS}, index=[0])
    sig.loc[0, "price_anchor"] = 1.0  # solo trend disponibile
    comps = combine(sig, "swing")
    assert comps.loc[0, "score"] == pytest.approx(100.0)


def test_snapshot_favorable_means_buying_the_instrument() -> None:
    sig = pd.Series({"price_anchor": 0.8, "rsi": 0.5, "rsi_extreme": -0.6, "obv": np.nan})
    comps = pd.Series(
        {"trend": 0.8, "momentum": -0.05, "volume": np.nan, "sentiment": np.nan, "score": 45.0}
    )
    long = snapshot(sig, comps)
    assert long.score == 45.0
    assert {e["key"] for e in long.favorable} == {"price_anchor", "rsi"}
    assert [e["key"] for e in long.contrary] == ["rsi_extreme"]
    assert long.contrary[0]["label"].startswith("RSI in ipercomprato")
    short = snapshot(sig, comps, direction=-1.0)
    assert short.score == -45.0
    # Per uno short il sottostante sopra la media è contrario all'acquisto.
    assert {e["key"] for e in short.contrary} == {"price_anchor", "rsi"}
    assert [e["key"] for e in short.favorable] == ["rsi_extreme"]
    assert all(float(e["value"]) > 0 for e in short.favorable)


def test_signals_have_no_lookahead() -> None:
    df = trending()
    full = elementary_signals(df, "swing", Calendar.ALWAYS)
    part = elementary_signals(df.iloc[:300], "swing", Calendar.ALWAYS)
    pd.testing.assert_frame_equal(full.iloc[:300], part, check_freq=False)


def test_sentiment_known_only_after_day_closes() -> None:
    daily = pd.Series([0.5, -0.5], index=pd.DatetimeIndex(["2026-01-05", "2026-01-06"]))
    bars = pd.DatetimeIndex(["2026-01-05 15:00", "2026-01-06 15:00", "2026-01-07 15:00"], tz="UTC")
    s = align_sentiment(daily, bars, days=1)
    assert np.isnan(s.iloc[0])  # il sentiment del 5 non è ancora noto il 5
    assert s.iloc[1] == 0.5
    assert s.iloc[2] == -0.5
    stale = align_sentiment(daily, pd.DatetimeIndex(["2026-02-20"], tz="UTC"), days=1)
    assert np.isnan(stale.iloc[0])
