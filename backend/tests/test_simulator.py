from datetime import UTC, datetime

import pandas as pd
import pytest

from app.trading.simulator import Entry, find_entry, find_exit, pnl


def bars(
    rows: list[tuple[float, float, float, float]], start: str = "2026-10-12", freq: str = "D"
) -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def test_entry_is_next_bar_open() -> None:
    b = bars([(100, 101, 99, 100), (102, 103, 101, 102)])
    e = find_entry(b, b.index[0].to_pydatetime())
    assert e is not None and e.price == 102 and e.ts == b.index[1]
    assert find_entry(b, b.index[1].to_pydatetime()) is None


def test_stop_target_and_both_in_same_bar() -> None:
    e = Entry(datetime(2026, 10, 12, tzinfo=UTC), 100.0)
    stop = find_exit(bars([(100, 101, 99, 100), (100, 100.5, 94, 96)]), e, 95, 110, 20)
    assert stop is not None and (stop.reason, stop.price) == ("stop", 95)
    target = find_exit(bars([(100, 101, 99, 100), (104, 111, 103, 108)]), e, 95, 110, 20)
    assert target is not None and (target.reason, target.price) == ("obiettivo", 110)
    both = find_exit(bars([(100, 112, 94, 100)]), e, 95, 110, 20)
    assert both is not None and both.reason == "stop"  # ipotesi prudente


def test_gap_through_stop_exits_at_worse_open() -> None:
    e = Entry(datetime(2026, 10, 12, tzinfo=UTC), 100.0)
    out = find_exit(bars([(100, 101, 99, 100), (90, 92, 89, 91)]), e, 95, 110, 20)
    assert out is not None and (out.reason, out.price) == ("stop", 90)


def test_time_exit_and_session_end() -> None:
    e = Entry(datetime(2026, 10, 12, tzinfo=UTC), 100.0)
    flat = [(100, 101, 99, 100)] * 5
    out = find_exit(bars(flat), e, 95, 110, max_bars=3)
    assert out is not None and out.reason == "tempo" and out.ts == bars(flat).index[2]
    two_days = bars([(100, 101, 99, 100)] * 4, start="2026-10-12 23:30", freq="15min")
    out3 = find_exit(two_days, Entry(two_days.index[0].to_pydatetime(), 100.0), 95, 110, 26, True)
    assert out3 is not None and out3.ts == two_days.index[1]  # ultima candela del 12


def test_open_trade_without_exit() -> None:
    e = Entry(datetime(2026, 10, 12, tzinfo=UTC), 100.0)
    assert find_exit(bars([(100, 101, 99, 100)] * 3), e, 95, 110, 20) is None


def test_pnl_includes_costs_on_both_sides() -> None:
    net, fees = pnl(200.0, 100.0, 110.0, 0.0025)
    assert fees == pytest.approx(200 * 0.0025 + 220 * 0.0025)
    assert net == pytest.approx(20 - fees)
