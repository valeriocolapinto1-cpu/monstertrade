from datetime import UTC, datetime

import pandas as pd

from app.data.models import Timeframe
from app.data.quality import check, expected_index
from app.data.universe import Calendar
from app.jobs.prices import drop_incomplete
from tests.conftest import ohlcv


def nyse_sessions(start: str, end: str) -> pd.DatetimeIndex:
    return expected_index(
        Calendar.NYSE, Timeframe.D1, pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    )


def test_nyse_calendar_skips_weekends_and_holidays() -> None:
    sessions = nyse_sessions("2026-07-01", "2026-07-08")
    days = [d.strftime("%m-%d") for d in sessions]
    assert "07-03" not in days  # festività osservata per il 4 luglio (sabato)
    assert "07-04" not in days and "07-05" not in days
    assert days == ["07-01", "07-02", "07-06", "07-07", "07-08"]


def test_missing_session_is_detected() -> None:
    sessions = nyse_sessions("2026-09-01", "2026-09-30")
    frame = ohlcv(sessions.delete(5), [100.0] * (len(sessions) - 1))
    report = check("SPX", frame, Timeframe.D1, Calendar.NYSE)
    assert [t.date() for t in report.missing] == [sessions[5].date()]
    assert not report.complete


def test_tail_gap_detected_with_expected_end() -> None:
    sessions = nyse_sessions("2026-09-01", "2026-09-30")
    frame = ohlcv(sessions[:-2], [100.0] * (len(sessions) - 2))
    report = check(
        "SPX", frame, Timeframe.D1, Calendar.NYSE, expected_end=pd.Timestamp("2026-09-30", tz="UTC")
    )
    assert len(report.missing) == 2


def test_intraday_nyse_half_day() -> None:
    bars = expected_index(
        Calendar.NYSE,
        Timeframe.M15,
        pd.Timestamp("2026-11-27", tz="UTC"),
        pd.Timestamp("2026-11-28", tz="UTC"),
    )
    # Venerdì dopo il Ringraziamento: chiusura alle 13:00 ET = 14:30-18:00 UTC.
    assert len(bars) == 14
    assert bars[0] == pd.Timestamp("2026-11-27 14:30", tz="UTC")


def test_crypto_every_day() -> None:
    idx = pd.date_range("2026-01-01", "2026-01-10", freq="D", tz="UTC")
    frame = ohlcv(idx.delete([3, 4]), [1.0] * 8)
    report = check("BTC", frame, Timeframe.D1, Calendar.ALWAYS)
    assert len(report.missing) == 2


def test_invalid_and_outliers() -> None:
    idx = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    closes = [100.0 + (i % 3) * 0.5 for i in range(60)]
    closes[40] = 150.0
    frame = ohlcv(idx, closes)
    frame.loc[idx[10], "high"] = frame.loc[idx[10], "low"] - 1
    report = check("BTC", frame, Timeframe.D1, Calendar.ALWAYS)
    assert report.invalid == [idx[10].to_pydatetime()]
    assert idx[40].to_pydatetime() in report.outliers
    assert not report.complete


def test_drop_incomplete_daily_nyse_and_intraday() -> None:
    idx = pd.DatetimeIndex(["2026-10-15", "2026-10-16"], tz="UTC")
    frame = ohlcv(idx, [1.0, 2.0])
    during = datetime(2026, 10, 16, 18, tzinfo=UTC)  # mercato aperto
    after = datetime(2026, 10, 16, 21, tzinfo=UTC)
    assert len(drop_incomplete(frame, Timeframe.D1, Calendar.NYSE, during)) == 1
    assert len(drop_incomplete(frame, Timeframe.D1, Calendar.NYSE, after)) == 2
    bars = pd.date_range("2026-10-16 14:00", periods=3, freq="5min", tz="UTC")
    now = datetime(2026, 10, 16, 14, 12, tzinfo=UTC)
    kept = drop_incomplete(ohlcv(bars, [1.0, 2.0, 3.0]), Timeframe.M5, Calendar.ALWAYS, now)
    assert len(kept) == 2
