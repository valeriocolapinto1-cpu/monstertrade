import pandas as pd
import pytest

from app.data.synthetic import BASE_LEVEL, synthesize_daily, synthesize_intraday
from tests.conftest import ohlcv


def daily(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-05", periods=len(closes), freq="D", tz="UTC")
    return ohlcv(idx, closes)


def test_three_x_daily_returns_without_costs() -> None:
    under = daily([100.0, 101.0, 99.99])
    synth = synthesize_daily(under, leverage=3, ter=0, funding=0)
    returns = synth["close"].pct_change().dropna().tolist()
    assert returns == pytest.approx([0.03, -0.03])
    assert synth["close"].iloc[0] == BASE_LEVEL


def test_short_swaps_high_and_low() -> None:
    under = daily([100.0, 102.0])
    synth = synthesize_daily(under, leverage=-3, ter=0, funding=0)
    assert synth["close"].iloc[1] == pytest.approx(BASE_LEVEL * (1 - 0.06))
    # Il massimo dello short corrisponde al minimo del sottostante.
    expected_high = BASE_LEVEL * (1 - 3 * (102 * 0.99 / 100 - 1))
    assert synth["high"].iloc[1] == pytest.approx(expected_high)
    assert (synth["high"] >= synth["low"]).all()


def test_volatility_decay_in_flat_market() -> None:
    # Sottostante che oscilla e torna al punto di partenza: il 3x perde valore.
    under = daily([100.0, 110.0, 100.0, 110.0, 100.0])
    synth = synthesize_daily(under, leverage=3, ter=0, funding=0)
    assert synth["close"].iloc[-1] < BASE_LEVEL * 0.95


def test_costs_accrue_on_calendar_days() -> None:
    under = daily([100.0] * 366)
    synth = synthesize_daily(under, leverage=3, ter=0.0075, funding=0.04)
    # Un anno: (1 - 3) * 4% - 0,75% = -8,75% circa (composto giornalmente).
    assert synth["close"].iloc[-1] / BASE_LEVEL - 1 == pytest.approx(-0.0838, abs=0.002)


def test_wipeout_is_floored_not_negative() -> None:
    under = daily([100.0, 60.0, 61.0])  # -40% in un giorno con leva 3
    synth = synthesize_daily(under, leverage=3, ter=0, funding=0)
    assert (synth["close"] > 0).all()
    assert synth["close"].iloc[1] < 1e-3


def test_intraday_resets_on_previous_daily_close() -> None:
    under_daily = daily([100.0, 102.0])
    synth_daily = synthesize_daily(under_daily, leverage=2, ter=0, funding=0)
    idx = pd.date_range("2026-01-06 14:30", periods=3, freq="5min", tz="UTC")
    under_intraday = ohlcv(idx, [100.0, 101.0, 102.0])
    out = synthesize_intraday(under_intraday, under_daily, synth_daily, leverage=2)
    assert out["close"].tolist() == pytest.approx([100.0, 102.0, 104.0])
    assert out["close"].iloc[-1] == pytest.approx(synth_daily["close"].iloc[1])


def test_intraday_without_previous_session_is_dropped() -> None:
    under_daily = daily([100.0])
    synth_daily = synthesize_daily(under_daily, leverage=2, ter=0, funding=0)
    idx = pd.date_range("2026-01-05 14:30", periods=2, freq="5min", tz="UTC")
    out = synthesize_intraday(ohlcv(idx, [100.0, 101.0]), under_daily, synth_daily, 2)
    assert out.empty


def test_intraday_short_never_negative() -> None:
    under_daily = daily([100.0, 100.0])
    synth_daily = synthesize_daily(under_daily, leverage=-3, ter=0, funding=0)
    idx = pd.date_range("2026-01-06 14:30", periods=2, freq="5min", tz="UTC")
    out = synthesize_intraday(ohlcv(idx, [140.0, 150.0]), under_daily, synth_daily, -3)
    assert (out[["open", "high", "low", "close"]] > 0).all().all()


def test_series_anchored_to_fixed_date() -> None:
    idx = pd.date_range("2024-12-30", periods=6, freq="D", tz="UTC")
    under = ohlcv(idx, [100.0, 90.0, 95.0, 99.0, 101.0, 103.0])
    synth = synthesize_daily(under, leverage=-3, ter=0, funding=0)
    assert synth.loc["2025-01-02", "close"] == pytest.approx(BASE_LEVEL)
    returns = synth["close"].pct_change().dropna()
    assert returns.iloc[0] == pytest.approx(0.30)
