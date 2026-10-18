"""Backtest dello score contro le strategie semplici della Fase 2.

Regola: si entra quando lo score (con il segno dello strumento) supera ENTER_SCORE e si
esce quando scende sotto EXIT_SCORE.
Stessi costi, stessa esecuzione all'apertura successiva, stesse finestre di dati.
Il sentiment entra solo dove esiste uno storico (Fear and Greed per le crypto dal
2018); per gli indici il backtest misura la parte tecnica dello score.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import Engine

from app.analysis.backtest import HORIZONS, Result, Strategy, evaluate
from app.analysis.costs import cost_model
from app.analysis.scoring import build
from app.analysis.signals import ENTER_SCORE, EXIT_SCORE, HORIZON_TIMEFRAME, hysteresis
from app.data.universe import UNIVERSE


def score_strategy(
    score: pd.Series, enter: float = ENTER_SCORE, exit_: float = EXIT_SCORE
) -> Strategy:
    held = hysteresis(score, enter, exit_)

    def signal(df: pd.DataFrame) -> pd.Series:
        return held.reindex(df.index).fillna(False).astype(bool)

    return Strategy("score", f"Score: entra > {enter:.0f}, esce < {exit_:.0f}", "score", signal)


@dataclass
class Comparison:
    horizon: str
    instruments: int
    score_sharpe: float
    simple_sharpe: float
    best_simple_sharpe: float
    beats_best: int
    beats_average: int
    score_return: float
    simple_return: float

    @property
    def improves(self) -> bool:
        return self.score_sharpe > self.simple_sharpe and self.beats_average > self.instruments / 2


def run_scores(engine: Engine) -> list[Result]:
    results: list[Result] = []
    with engine.connect() as conn:
        for spec in UNIVERSE:
            costs = cost_model(spec)
            for horizon in HORIZON_TIMEFRAME:
                frame = build(conn, spec, horizon)
                if frame is None or len(frame.prices) < 200:
                    continue
                tf = HORIZONS[horizon][0]
                strategy = score_strategy(frame.score)
                results.append(
                    evaluate(
                        spec.symbol,
                        horizon,
                        frame.prices,
                        strategy,
                        costs.per_side,
                        tf,
                        spec.calendar,
                    )
                )
    return results


def compare(score_rows: list[Result], simple_rows: list[Result]) -> list[Comparison]:
    out: list[Comparison] = []
    for horizon in HORIZON_TIMEFRAME:
        scores = {r.symbol: r for r in score_rows if r.horizon == horizon}
        simple = [r for r in simple_rows if r.horizon == horizon and r.family != "riferimento"]
        if not scores:
            continue
        by_symbol: dict[str, list[Result]] = {}
        for r in simple:
            by_symbol.setdefault(r.symbol, []).append(r)
        symbols = [s for s in scores if s in by_symbol]

        def sharpe(r: Result) -> float:
            return r.sharpe if np.isfinite(r.sharpe) else 0.0

        beats_best = sum(sharpe(scores[s]) > max(sharpe(r) for r in by_symbol[s]) for s in symbols)
        beats_avg = sum(
            sharpe(scores[s]) > float(np.mean([sharpe(r) for r in by_symbol[s]])) for s in symbols
        )
        out.append(
            Comparison(
                horizon=horizon,
                instruments=len(symbols),
                score_sharpe=float(np.mean([sharpe(scores[s]) for s in symbols])),
                simple_sharpe=float(np.mean([sharpe(r) for s in symbols for r in by_symbol[s]])),
                best_simple_sharpe=float(
                    np.mean([max(sharpe(r) for r in by_symbol[s]) for s in symbols])
                ),
                beats_best=int(beats_best),
                beats_average=int(beats_avg),
                score_return=float(np.median([scores[s].total_return for s in symbols])),
                simple_return=float(
                    np.median([r.total_return for s in symbols for r in by_symbol[s]])
                ),
            )
        )
    return out
