import numpy as np
import pandas as pd
import pytest

from app.analysis.backtest import Strategy, buy_and_hold, evaluate, positions, run
from app.analysis.costs import cost_model
from app.data.models import Timeframe
from app.data.universe import BY_SYMBOL, Calendar


def frame(closes: list[float], opens: list[float] | None = None) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D", tz="UTC")
    close = pd.Series(closes, index=idx)
    open_ = pd.Series(opens if opens else closes, index=idx)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close),
            "low": np.minimum(open_, close),
            "close": close,
            "volume": 1.0,
        }
    )


def test_execution_happens_at_next_open() -> None:
    # Segnale "compra" alla chiusura della candela 0: si entra all'apertura della 1 (a 10).
    df = frame([100, 110, 121], opens=[100, 10, 120])
    strat = Strategy("x", "x", "trend", lambda d: pd.Series([True, True, True], index=d.index))
    pf = run(df, strat, 0.0, Timeframe.D1, Calendar.ALWAYS)
    assert pf.orders.price.values[0] == pytest.approx(10.0)


def test_future_data_does_not_change_past_signals() -> None:
    """Un salto enorme nel futuro non deve cambiare le operazioni passate."""
    base = [100 + i for i in range(60)]
    shocked = [*base[:-1], 1000.0]
    strat = Strategy("s", "s", "trend", lambda d: d["close"] > d["close"].rolling(5).mean())
    a = run(frame(base), strat, 0.0, Timeframe.D1, Calendar.ALWAYS).orders.records_readable
    b = run(frame(shocked), strat, 0.0, Timeframe.D1, Calendar.ALWAYS).orders.records_readable
    pd.testing.assert_frame_equal(a.iloc[: len(a)], b.iloc[: len(a)])


def test_costs_reduce_returns_exactly() -> None:
    df = frame([100.0] * 10)
    strat = Strategy("bh", "bh", "riferimento", buy_and_hold)
    free = evaluate("X", "swing", df, strat, 0.0, Timeframe.D1, Calendar.ALWAYS)
    paid = evaluate("X", "swing", df, strat, 0.01, Timeframe.D1, Calendar.ALWAYS)
    assert free.total_return == pytest.approx(0.0)
    assert paid.total_return == pytest.approx(-0.01 / 1.01, rel=1e-3)
    assert paid.costs_paid > 0


def test_day_trading_is_flat_at_session_end() -> None:
    idx = pd.date_range("2026-10-15 13:30", periods=4, freq="15min", tz="UTC").append(
        pd.date_range("2026-10-16 13:30", periods=4, freq="15min", tz="UTC")
    )
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx
    )
    pos = positions(df, buy_and_hold, flat_at_session_end=True)
    assert pos.tolist() == [True, True, True, False, True, True, True, False]


def test_cost_model_includes_fx_for_non_euro() -> None:
    assert cost_model(BY_SYMBOL["SPX3L"]).per_side == pytest.approx(0.0025)
    assert cost_model(BY_SYMBOL["NDX2L"]).per_side == pytest.approx(0.0010)  # quotato in EUR
    assert cost_model(BY_SYMBOL["BTC"]).round_trip == pytest.approx(0.008)
