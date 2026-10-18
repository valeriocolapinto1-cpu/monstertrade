from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.sentiment.scorer import Scorer
from app.sentiment.sources import Item


@dataclass(frozen=True)
class DailySentiment:
    symbol: str
    day: date
    source: str
    score: float
    mentions: int


def score_items(items: list[Item], scorer: Scorer) -> list[float]:
    """Usa il valore già noto (etichetta utente, indice) e FinBERT solo per il resto."""
    pending = [i for i, item in enumerate(items) if item.value is None and item.text]
    scores = [item.value if item.value is not None else 0.0 for item in items]
    for idx, value in zip(pending, scorer.score([items[i].text for i in pending]), strict=True):
        scores[idx] = value
    return scores


def daily(items: list[Item], scores: list[float]) -> list[DailySentiment]:
    groups: dict[tuple[str, date, str], list[float]] = defaultdict(list)
    for item, value in zip(items, scores, strict=True):
        groups[(item.symbol, item.ts.date(), item.source)].append(value)
    return [
        DailySentiment(sym, day, src, max(-1.0, min(1.0, sum(v) / len(v))), len(v))
        for (sym, day, src), v in sorted(groups.items())
    ]
