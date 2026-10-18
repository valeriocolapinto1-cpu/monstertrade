"""Calcolo e salvataggio degli indicatori per tutto l'universo.

Uso:  python -m app.jobs.indicators

Si salvano solo le ultime candele (servono al motore dei segnali): i grafici
calcolano gli indicatori al volo dai prezzi.
"""

import logging

from sqlalchemy import Engine

from app.analysis.compute import compute_all
from app.data.models import Timeframe
from app.data.universe import BY_SYMBOL, UNIVERSE
from app.db import repository as repo
from app.db.engine import get_engine

log = logging.getLogger("jobs.indicators")

KEEP = {Timeframe.D1: 500, Timeframe.M15: 300, Timeframe.M5: 300}
WARMUP = 400


def run(engine: Engine) -> int:
    total = 0
    with engine.begin() as conn:
        ids = repo.instrument_ids(conn)
        for spec in UNIVERSE:
            if spec.symbol not in ids:
                continue
            for tf, keep in KEEP.items():
                prices = repo.load_prices(conn, ids[spec.symbol], tf, limit=keep + WARMUP)
                if prices.empty:
                    continue
                under = None
                if spec.underlying and spec.underlying in ids:
                    under_spec = BY_SYMBOL[spec.underlying]
                    under = repo.load_prices(conn, ids[under_spec.symbol], tf, limit=keep + WARMUP)[
                        "close"
                    ]
                wide = compute_all(prices, tf, spec.calendar, spec.leverage, under).tail(keep)
                total += repo.replace_indicators(conn, ids[spec.symbol], tf, wide)
            log.info("%s: indicatori aggiornati", spec.symbol)
    return total


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    rows = run(get_engine())
    log.info("righe salvate: %d", rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
