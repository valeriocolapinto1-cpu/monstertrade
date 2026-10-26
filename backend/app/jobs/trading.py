"""Proposte di trade e simulazione (paper trading).

Uso:  python -m app.jobs.trading
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import Engine

from app.config import get_settings
from app.db.engine import get_engine
from app.trading.engine import evaluate, risk_config, save_proposals, simulate
from app.trading.notify import notify
from app.trading.risk import TradePlan

log = logging.getLogger("jobs.trading")


def run(engine: Engine, now: datetime | None = None, send: bool = True) -> dict[str, int]:
    now = now or datetime.now(UTC)
    settings = get_settings()
    cfg = risk_config(settings)
    with engine.begin() as conn:
        counts = simulate(conn, now)
    with engine.begin() as conn:
        candidates, state = evaluate(conn, cfg)
        created = save_proposals(conn, candidates, now)
    # Nei log del job: perché ogni candidato è stato proposto o scartato.
    log.info(
        "stato: capitale %.2f, posizioni e proposte %d, fonte %s",
        state.equity,
        len(state.open_positions),
        state.source,
    )
    for c in candidates:
        esito = (
            f"proposta {c.outcome.size_eur:.2f} €"
            if isinstance(c.outcome, TradePlan)
            else f"scartato: {c.outcome.reason}"
        )
        log.info("%s %s score %.0f: %s", c.spec.symbol, c.horizon, c.score, esito)
    counts["proposte"] = len(created)
    if send and created:
        topic = settings.ntfy_topic.get_secret_value() if settings.ntfy_topic else None
        lines = [
            f"{c.spec.name} ({c.horizon}) · {c.outcome.size_eur:.0f} € · rischio "
            f"{c.signal['risk_label']}"
            for c in candidates
            if isinstance(c.outcome, TradePlan)
        ]
        notify(topic, f"{len(created)} nuove proposte", "\n".join(lines[: len(created)]))
    log.info("trading: %s", counts)
    return counts


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    run(get_engine())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
