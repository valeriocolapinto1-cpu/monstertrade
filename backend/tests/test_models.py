import pandas as pd

from app.data.models import Timeframe, normalize_ohlcv, resample_weekly
from tests.conftest import ohlcv


def test_normalize_sorts_dedups_and_sets_utc() -> None:
    idx = pd.DatetimeIndex(["2026-01-02", "2026-01-01", "2026-01-02"])
    frame = ohlcv(idx, [2.0, 1.0, 3.0])
    out = normalize_ohlcv(frame)
    assert str(out.index.tz) == "UTC"
    assert out.index.is_monotonic_increasing
    assert out["close"].tolist() == [1.0, 3.0]  # tiene l'ultimo duplicato


def test_weekly_resample_starts_monday() -> None:
    idx = pd.date_range("2026-10-05", "2026-10-16", freq="B", tz="UTC")  # due settimane
    frame = ohlcv(idx, [float(i) for i in range(1, 11)])
    weekly = resample_weekly(frame)
    assert list(weekly.index.day_name()) == ["Monday", "Monday"]
    assert weekly["open"].tolist() == [1.0, 6.0]
    assert weekly["close"].tolist() == [5.0, 10.0]
    assert weekly["volume"].tolist() == [5.0, 5.0]


def test_timeframe_properties() -> None:
    assert not Timeframe.W1.stored
    assert Timeframe.M5.intraday and not Timeframe.D1.intraday
    assert Timeframe.M15.minutes == 15
