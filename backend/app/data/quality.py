"""Controllo di qualità delle candele: buchi, duplicati, valori impossibili e anomali."""

from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from app.data.models import Timeframe
from app.data.universe import Calendar

# Rendimento anomalo: oltre 12 deviazioni robuste e oltre il 10% in una candela.
OUTLIER_Z = 12.0
OUTLIER_MIN_MOVE = 0.10


@dataclass
class QualityReport:
    symbol: str
    timeframe: str
    rows: int
    first: datetime | None
    last: datetime | None
    missing: list[datetime] = field(default_factory=list)
    duplicates: int = 0
    invalid: list[datetime] = field(default_factory=list)
    outliers: list[datetime] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.rows > 0 and not self.missing and not self.duplicates and not self.invalid

    def summary(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "rows": self.rows,
            "first": self.first.isoformat() if self.first else None,
            "last": self.last.isoformat() if self.last else None,
            "missing": len(self.missing),
            "missing_sample": [t.isoformat() for t in self.missing[:10]],
            "duplicates": self.duplicates,
            "invalid": len(self.invalid),
            "outliers": [t.isoformat() for t in self.outliers[:20]],
            "complete": self.complete,
        }


@lru_cache(maxsize=4)
def _calendar(code: str) -> xcals.ExchangeCalendar:
    return xcals.get_calendar(code, start="1990-01-01")


def expected_index(
    calendar: Calendar, timeframe: Timeframe, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DatetimeIndex:
    """Inizi di candela attesi in [start, end] secondo il calendario di negoziazione."""
    step = pd.Timedelta(minutes=timeframe.minutes)
    if calendar is Calendar.ALWAYS:
        freq = "D" if timeframe is Timeframe.D1 else step
        first = start.floor("D") if timeframe is Timeframe.D1 else start
        return pd.date_range(first, end, freq=freq, tz="UTC")
    cal = _calendar(calendar.value)
    first_day = max(start.tz_convert(None).normalize(), cal.first_session)
    last_day = min(end.tz_convert(None).normalize(), cal.last_session)
    if first_day > last_day:
        return pd.DatetimeIndex([], tz="UTC")
    sessions = cal.sessions_in_range(first_day, last_day)
    if timeframe is Timeframe.D1:
        return pd.DatetimeIndex(sessions).tz_localize("UTC")
    schedule = cal.schedule.loc[sessions]
    bars: list[pd.DatetimeIndex] = [
        pd.date_range(row.open, row.close - step, freq=step)
        for row in schedule.itertuples()
    ]
    index = bars[0].append(bars[1:]) if bars else pd.DatetimeIndex([], tz="UTC")
    index = pd.DatetimeIndex(index).tz_convert("UTC")
    return index[(index >= start) & (index <= end)]


def check(
    symbol: str,
    frame: pd.DataFrame,
    timeframe: Timeframe,
    calendar: Calendar,
    expected_end: pd.Timestamp | None = None,
) -> QualityReport:
    """Controlla `frame`; `expected_end` estende il controllo fino a una data attesa."""
    if frame.empty:
        return QualityReport(symbol, timeframe.value, 0, None, None)
    index = pd.DatetimeIndex(frame.index)
    report = QualityReport(
        symbol,
        timeframe.value,
        rows=len(frame),
        first=index.min().to_pydatetime(),
        last=index.max().to_pydatetime(),
        duplicates=int(index.duplicated().sum()),
    )
    end = max(index.max(), expected_end) if expected_end is not None else index.max()
    expected = expected_index(calendar, timeframe, index.min(), end)
    report.missing = [t.to_pydatetime() for t in expected.difference(index)]

    o, h, low, c = (frame[col] for col in ("open", "high", "low", "close"))
    bad = (
        (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (h < low)
        | (h < np.maximum(o, c) - 1e-9 * h)
        | (low > np.minimum(o, c) + 1e-9 * low)
        | frame[["open", "high", "low", "close"]].isna().any(axis=1)
    )
    report.invalid = [t.to_pydatetime() for t in frame.index[bad]]

    log_ret = pd.Series(np.log(c.to_numpy()), index=frame.index).diff().dropna()
    if len(log_ret) > 30:
        median = log_ret.median()
        mad = (log_ret - median).abs().median() * 1.4826
        if mad > 0:
            z = (log_ret - median).abs() / mad
            flagged = log_ret[(z > OUTLIER_Z) & (log_ret.abs() > np.log1p(OUTLIER_MIN_MOVE))]
            report.outliers = [t.to_pydatetime() for t in flagged.index]
    return report
