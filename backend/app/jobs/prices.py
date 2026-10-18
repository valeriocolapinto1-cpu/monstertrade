"""Scarico dello storico e aggiornamento periodico dei prezzi.

Uso:  python -m app.jobs.prices update     (storico al primo avvio, poi incrementale)
      python -m app.jobs.prices quality    (rapporto di qualità in JSON)
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime, timedelta

import httpx
import pandas as pd
from sqlalchemy import Connection, Engine

from app.config import get_settings
from app.data import quality
from app.data.models import Timeframe, normalize_ohlcv
from app.data.sources.registry import SourceRegistry
from app.data.synthetic import synthesize_daily, synthesize_intraday
from app.data.universe import (
    BY_SYMBOL,
    UNIVERSE,
    Calendar,
    InstrumentSpec,
    base_instruments,
    synthetic_instruments,
)
from app.db import repository as repo
from app.db.engine import get_engine

log = logging.getLogger("jobs.prices")

HISTORY_START = datetime(2000, 1, 1, tzinfo=UTC)
INTRADAY_RETENTION = timedelta(days=60)
OVERLAP = {
    Timeframe.D1: timedelta(days=7),
    Timeframe.M15: timedelta(days=2),
    Timeframe.M5: timedelta(days=2),
}
STORED = (Timeframe.D1, Timeframe.M15, Timeframe.M5)
# Ritardo tollerato prima di considerare mancante l'ultima candela attesa.
FRESHNESS = {
    Timeframe.D1: timedelta(hours=30),
    Timeframe.M15: timedelta(hours=2),
    Timeframe.M5: timedelta(hours=2),
}


def drop_incomplete(
    frame: pd.DataFrame, timeframe: Timeframe, calendar: Calendar, now: datetime
) -> pd.DataFrame:
    """Scarta le candele non ancora chiuse."""
    if frame.empty:
        return frame
    index = pd.DatetimeIndex(frame.index)
    if timeframe is Timeframe.D1 and calendar is Calendar.NYSE:
        cal = quality._calendar(calendar.value)
        closes = [
            cal.session_close(d) if cal.is_session(d) else d + pd.Timedelta(days=1)
            for d in index.tz_convert(None)
        ]
        end = pd.DatetimeIndex(closes).tz_convert("UTC")
    else:
        end = index + pd.Timedelta(minutes=timeframe.minutes)
    return frame[end <= pd.Timestamp(now)]


def update_base(
    conn: Connection,
    registry: SourceRegistry,
    spec: InstrumentSpec,
    ids: dict[str, int],
    now: datetime,
) -> list[str]:
    errors: list[str] = []
    for tf in STORED:
        last = repo.last_timestamp(conn, ids[spec.symbol], tf)
        floor = HISTORY_START if tf is Timeframe.D1 else now - INTRADAY_RETENTION
        start = max(floor, last - OVERLAP[tf]) if last else floor
        result = registry.fetch(spec, tf, start, now, now=now)
        errors.extend(result.errors)
        frame = drop_incomplete(normalize_ohlcv(result.frame), tf, spec.calendar, now)
        count = repo.upsert_prices(conn, ids[spec.symbol], tf, frame, result.source)
        if tf.intraday:
            repo.delete_before(conn, ids[spec.symbol], tf, now - INTRADAY_RETENTION)
        log.info("%s %s: %d candele da %s", spec.symbol, tf, count, result.source or "-")
    return errors


def update_synthetic(
    conn: Connection, spec: InstrumentSpec, ids: dict[str, int], funding: float
) -> None:
    if spec.underlying is None:
        raise ValueError(f"{spec.symbol} non ha un sottostante")
    under_id = ids[spec.underlying]
    under_daily = repo.load_prices(conn, under_id, Timeframe.D1)
    daily = synthesize_daily(under_daily, spec.leverage, spec.ter, funding)
    repo.upsert_prices(conn, ids[spec.symbol], Timeframe.D1, daily, "sintetico")
    for tf in (Timeframe.M15, Timeframe.M5):
        intraday = repo.load_prices(conn, under_id, tf)
        frame = synthesize_intraday(intraday, under_daily, daily, spec.leverage)
        repo.upsert_prices(conn, ids[spec.symbol], tf, frame, "sintetico")
        repo.delete_before(conn, ids[spec.symbol], tf, datetime.now(UTC) - INTRADAY_RETENTION)
    log.info("%s: serie sintetica aggiornata (%d giorni)", spec.symbol, len(daily))


def run_update(engine: Engine, registry: SourceRegistry, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    funding = get_settings().funding_rate
    errors: list[str] = []
    with engine.begin() as conn:
        ids = repo.sync_instruments(conn, UNIVERSE)
    for spec in base_instruments():
        with engine.begin() as conn:
            errors.extend(update_base(conn, registry, spec, ids, now))
    for spec in synthetic_instruments():
        with engine.begin() as conn:
            update_synthetic(conn, spec, ids, funding)
    return errors


def run_quality(engine: Engine, now: datetime | None = None) -> list[quality.QualityReport]:
    now = now or datetime.now(UTC)
    reports: list[quality.QualityReport] = []
    with engine.connect() as conn:
        ids = repo.instrument_ids(conn)
        for spec in UNIVERSE:
            if spec.symbol not in ids:
                continue
            for tf in STORED:
                frame = repo.load_prices(conn, ids[spec.symbol], tf)
                expected_end = pd.Timestamp(now - FRESHNESS[tf])
                reports.append(quality.check(spec.symbol, frame, tf, spec.calendar, expected_end))
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prezzi: scarico e qualità")
    parser.add_argument("command", choices=["update", "quality"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    # Gli URL delle richieste possono contenere chiavi API: mai nei log.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    engine = get_engine()
    if args.command == "update":
        with httpx.Client(headers={"User-Agent": "monstertrade/0.1"}) as client:
            registry = SourceRegistry.from_settings(get_settings(), client)
            errors = run_update(engine, registry)
        for err in errors:
            log.warning("fonte: %s", err)
        return 0
    reports = run_quality(engine)
    json.dump([r.summary() for r in reports], sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if all(r.complete for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["BY_SYMBOL", "main", "run_quality", "run_update"]
