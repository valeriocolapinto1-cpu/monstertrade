"""Calcolo e salvataggio degli score per strumento e orizzonte.

Uso:  python -m app.jobs.signals
"""

import logging
import math

from sqlalchemy import Engine

from app.analysis.risk_label import RiskInputs, risk_label
from app.analysis.scoring import atr_context, build
from app.analysis.signals import HORIZON_TIMEFRAME, snapshot
from app.data.universe import UNIVERSE
from app.db import repository as repo
from app.db.engine import get_engine

log = logging.getLogger("jobs.signals")

KEEP = 30
LOOKBACK = {"day": 700, "swing": 700, "long": 300}


def run(engine: Engine) -> int:
    total = 0
    with engine.begin() as conn:
        ids = repo.instrument_ids(conn)
        for spec in UNIVERSE:
            if spec.symbol not in ids:
                continue
            for horizon in HORIZON_TIMEFRAME:
                frame = build(conn, spec, horizon, LOOKBACK[horizon])
                if frame is None or frame.components["score"].dropna().empty:
                    continue
                atr_now, atr_median = atr_context(frame.prices)
                if math.isnan(atr_now):
                    continue
                label = risk_label(spec, RiskInputs(horizon, atr_now, atr_median))
                rows: list[dict[str, object]] = []
                valid = frame.components.dropna(subset=["score"]).tail(KEEP)
                for ts in valid.index:
                    snap = snapshot(
                        frame.signals.loc[ts], frame.components.loc[ts], frame.direction
                    )
                    rows.append(
                        {
                            "ts": ts.to_pydatetime(),
                            "score": snap.score,
                            "components": snap.components,
                            "favorable": snap.favorable,
                            "contrary": snap.contrary,
                            "risk_label": label,
                        }
                    )
                total += repo.replace_signals(conn, ids[spec.symbol], horizon, rows, KEEP)
            log.info("%s: score aggiornati", spec.symbol)
    return total


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    log.info("righe: %d", run(get_engine()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
