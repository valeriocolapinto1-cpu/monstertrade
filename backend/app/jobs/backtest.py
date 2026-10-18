"""Backtest delle strategie semplici su tutto l'universo.

Uso:  python -m app.jobs.backtest   (scrive il rapporto JSON in CACHE_DIR/backtest.json)
"""

import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from app.analysis.backtest import HORIZONS, Result, evaluate
from app.analysis.costs import cost_model
from app.config import get_settings
from app.data.models import Timeframe, resample_weekly
from app.data.universe import UNIVERSE, InstrumentSpec, Kind
from app.db import repository as repo
from app.db.engine import get_engine

log = logging.getLogger("jobs.backtest")

# Gli indici non si comprano direttamente: si testano come proxy di un ETF senza leva.
MIN_BARS = {"day": 500, "swing": 400, "long": 120}


def load(engine: Engine, spec: InstrumentSpec, timeframe: Timeframe) -> pd.DataFrame:
    with engine.connect() as conn:
        ids = repo.instrument_ids(conn)
        if spec.symbol not in ids:
            return pd.DataFrame()
        if timeframe is Timeframe.W1:
            return resample_weekly(repo.load_prices(conn, ids[spec.symbol], Timeframe.D1))
        return repo.load_prices(conn, ids[spec.symbol], timeframe)


def run_all(engine: Engine) -> list[Result]:
    results: list[Result] = []
    for spec in UNIVERSE:
        costs = cost_model(spec)
        for horizon, (timeframe, strategies) in HORIZONS.items():
            df = load(engine, spec, timeframe)
            if len(df) < MIN_BARS[horizon]:
                continue
            for strategy in strategies:
                results.append(
                    evaluate(
                        spec.symbol, horizon, df, strategy, costs.per_side, timeframe, spec.calendar
                    )
                )
        log.info("%s: backtest completato", spec.symbol)
    return results


def report_path() -> Path:
    return get_settings().cache_dir / "backtest.json"


def write_report(
    results: list[Result], path: Path, score_results: list[Result] | None = None
) -> dict[str, object]:
    from app.analysis.score_backtest import compare

    tradable = [r for r in results if r.family != "riferimento"]
    positive = [r for r in tradable if (r.total_return or 0) > 0]
    comparisons = compare(score_results, results) if score_results else []
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "criterion_met": bool(positive),
        "positive_strategies": len(positive),
        "tested_strategies": len(tradable),
        "score_improves": bool(comparisons) and all(c.improves for c in comparisons),
        "score_comparison": [{**asdict(c), "improves": c.improves} for c in comparisons],
        "results": [r.to_dict() for r in [*results, *(score_results or [])]],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return report


def run_report(engine: Engine) -> dict[str, object]:
    from app.analysis.score_backtest import run_scores

    return write_report(run_all(engine), report_path(), run_scores(engine))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    report = run_report(get_engine())
    log.info(
        "strategie positive dopo i costi: %s su %s; lo score migliora: %s",
        report["positive_strategies"],
        report["tested_strategies"],
        report["score_improves"],
    )
    return 0 if report["criterion_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Kind", "main", "run_all", "write_report"]
