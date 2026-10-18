"""Indicatori contro valori di riferimento pubblicati e contro la libreria `ta`."""

import numpy as np
import pandas as pd
import pytest
import ta

from app.analysis import indicators as ind
from app.analysis.compute import compute_all
from app.data.models import Timeframe
from app.data.universe import Calendar

# Esempio RSI di Wilder pubblicato da StockCharts (ChartSchool, "RSI").
RSI_CLOSES = [
    44.34,
    44.09,
    44.15,
    43.61,
    44.33,
    44.83,
    45.10,
    45.42,
    45.84,
    46.08,
    45.89,
    46.03,
    45.61,
    46.28,
    46.28,
    46.00,
    46.03,
    46.41,
    46.22,
    45.64,
]


def test_rsi_matches_published_wilder_example() -> None:
    out = ind.rsi(pd.Series(RSI_CLOSES))
    assert out.iloc[:14].isna().all()
    # Valore esatto: guadagno medio 3,34/14, perdita media 1,40/14.
    assert out.iloc[14] == pytest.approx(100 - 100 / (1 + 3.34 / 1.40), abs=1e-9)
    # StockCharts pubblica 70,53 e 66,32 arrotondando le medie intermedie.
    assert out.iloc[14] == pytest.approx(70.53, abs=0.1)
    assert out.iloc[15] == pytest.approx(66.32, abs=0.1)


def test_sma_and_ema_hand_computed() -> None:
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert ind.sma(s, 3).tolist()[2:] == [2.0, 3.0, 4.0]
    e = ind.ema(s, 3)  # seme = media dei primi 3, poi alpha = 0,5
    assert e.iloc[2] == 2.0 and e.iloc[3] == 3.0 and e.iloc[4] == 4.0


def test_true_range_uses_previous_close() -> None:
    df = pd.DataFrame({"high": [10.0, 12.0], "low": [9.0, 11.5], "close": [9.5, 12.0]})
    assert ind.true_range(df).tolist() == [1.0, 2.5]


def test_drawdown_sharpe_and_decay() -> None:
    close = pd.Series([100.0, 120.0, 90.0, 130.0])
    assert ind.max_drawdown(close) == pytest.approx(-0.25)
    returns = pd.Series([0.01, -0.01] * 50)
    assert ind.sharpe(returns, 252) == pytest.approx(0.0, abs=1e-9)
    assert ind.leverage_decay(0.2, 3) == pytest.approx(0.12)
    assert ind.leverage_decay(0.2, -3) == pytest.approx(0.24)
    assert ind.leverage_decay(0.2, 1) == 0


@pytest.fixture
def ohlc() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, 600)))
    high = close * (1 + rng.uniform(0, 0.01, 600))
    low = close * (1 - rng.uniform(0, 0.01, 600))
    open_ = np.r_[close[0], close[:-1]]
    idx = pd.date_range("2024-01-01", periods=600, freq="D", tz="UTC")
    volume = rng.uniform(1e5, 1e6, 600)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum.reduce([high, open_, close]),
            "low": np.minimum.reduce([low, open_, close]),
            "close": close,
            "volume": volume,
        },
        index=idx,
    )


def tail_close(a: pd.Series, b: pd.Series, n: int = 300, rel: float = 1e-6) -> None:
    np.testing.assert_allclose(a.tail(n).to_numpy(), b.tail(n).to_numpy(), rtol=rel, atol=1e-8)


def test_against_ta_library(ohlc: pd.DataFrame) -> None:
    c, h, low, v = ohlc["close"], ohlc["high"], ohlc["low"], ohlc["volume"]
    tail_close(ind.sma(c, 20), ta.trend.sma_indicator(c, 20))
    tail_close(ind.ema(c, 20), ta.trend.ema_indicator(c, 20))
    m = ind.macd(c)
    tail_close(m["macd"], ta.trend.macd(c))
    tail_close(m["macd_signal"], ta.trend.macd_signal(c))
    tail_close(ind.rsi(c), ta.momentum.rsi(c, 14), rel=1e-4)
    tail_close(ind.atr(ohlc), ta.volatility.average_true_range(h, low, c, 14), rel=1e-4)
    bb = ind.bollinger(c)
    tail_close(bb["bb_upper"], ta.volatility.bollinger_hband(c, 20, 2))
    tail_close(bb["bb_lower"], ta.volatility.bollinger_lband(c, 20, 2))
    st = ind.stochastic(ohlc, 14, 3, 3)
    tail_close(
        st["stoch_k"],
        ta.momentum.stoch(h, low, c, 14, 3)
        .rolling(1)
        .mean()
        .pipe(lambda s: ta.momentum.stoch(h, low, c, 14, 1).rolling(3).mean()),
    )
    tail_close(
        ind.obv(ohlc) - ind.obv(ohlc).iloc[0],
        ta.volume.on_balance_volume(c, v) - ta.volume.on_balance_volume(c, v).iloc[0],
    )
    adx_ref = ta.trend.ADXIndicator(h, low, c, 14)
    tail_close(ind.adx(ohlc)["plus_di"], adx_ref.adx_pos(), rel=1e-3)
    tail_close(ind.adx(ohlc)["adx"], adx_ref.adx(), rel=1e-3)


def test_no_lookahead(ohlc: pd.DataFrame) -> None:
    """Il valore a t non cambia aggiungendo candele future."""
    full = compute_all(ohlc, Timeframe.D1, Calendar.ALWAYS, leverage=3)
    partial = compute_all(ohlc.iloc[:400], Timeframe.D1, Calendar.ALWAYS, leverage=3)
    pd.testing.assert_frame_equal(full.iloc[:400], partial, check_freq=False)


def test_vwap_resets_each_day() -> None:
    idx = pd.DatetimeIndex(["2026-01-05 10:00", "2026-01-05 10:05", "2026-01-06 10:00"], tz="UTC")
    df = pd.DataFrame(
        {
            "high": [11.0, 13.0, 21.0],
            "low": [9.0, 11.0, 19.0],
            "close": [10.0, 12.0, 20.0],
            "volume": [1.0, 3.0, 2.0],
        },
        index=idx,
    )
    assert ind.vwap(df).tolist() == pytest.approx([10.0, 11.5, 20.0])


def test_levels_and_fibonacci(ohlc: pd.DataFrame) -> None:
    levels = ind.support_resistance(ohlc)
    last = ohlc["close"].iloc[-1]
    assert levels
    assert all((lv.price < last) == (lv.kind == "supporto") for lv in levels)
    fib = ind.fibonacci(ohlc)
    assert fib is not None and set(fib) >= {"0.0", "38.2", "61.8", "100.0"}
    lo, hi = ohlc["low"].tail(120).min(), ohlc["high"].tail(120).max()
    assert {round(fib["0.0"], 6), round(fib["100.0"], 6)} == {round(lo, 6), round(hi, 6)}
