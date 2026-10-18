"""Punteggio di sentiment dei testi in [-1, 1].

FinBERT (ProsusAI/finbert) gira in locale con revisione del modello fissata; se le
librerie ML non sono installate (ad esempio sull'API) si usa un lessico finanziario
minimo, più grezzo ma deterministico.
"""

import re
from functools import lru_cache
from typing import Any, Protocol

FINBERT_MODEL = "ProsusAI/finbert"
FINBERT_REVISION = "0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031"


class Scorer(Protocol):
    name: str

    def score(self, texts: list[str]) -> list[float]: ...


class FinBertScorer:
    name = "finbert"

    def __init__(self, batch_size: int = 16) -> None:
        self.batch_size = batch_size
        self._pipeline: Any = None

    def _load(self) -> Any:
        if self._pipeline is None:
            from transformers import pipeline

            self._pipeline = pipeline(
                "text-classification",
                model=FINBERT_MODEL,
                revision=FINBERT_REVISION,
                top_k=None,
                truncation=True,
                max_length=256,
            )
        return self._pipeline

    def score(self, texts: list[str]) -> list[float]:
        if not texts:
            return []
        results = self._load()(texts, batch_size=self.batch_size)
        return [_finbert_to_score(r) for r in results]


def _finbert_to_score(labels: list[dict[str, Any]]) -> float:
    probs = {d["label"]: float(d["score"]) for d in labels}
    return probs.get("positive", 0.0) - probs.get("negative", 0.0)


POSITIVE = {
    "beat",
    "beats",
    "bullish",
    "gain",
    "gains",
    "growth",
    "high",
    "higher",
    "jump",
    "jumps",
    "outperform",
    "rally",
    "rallies",
    "rebound",
    "record",
    "rise",
    "rises",
    "soar",
    "soars",
    "strong",
    "surge",
    "surges",
    "upgrade",
    "upbeat",
}
NEGATIVE = {
    "bearish",
    "crash",
    "crashes",
    "cut",
    "decline",
    "declines",
    "downgrade",
    "drop",
    "drops",
    "fall",
    "falls",
    "fear",
    "loss",
    "losses",
    "lower",
    "miss",
    "misses",
    "plunge",
    "plunges",
    "recession",
    "selloff",
    "slump",
    "slumps",
    "tumble",
    "tumbles",
    "weak",
}
_WORD = re.compile(r"[a-z]+")


class LexiconScorer:
    name = "lessico"

    def score(self, texts: list[str]) -> list[float]:
        out: list[float] = []
        for text in texts:
            words = _WORD.findall(text.lower())
            pos = sum(w in POSITIVE for w in words)
            neg = sum(w in NEGATIVE for w in words)
            out.append(0.0 if pos + neg == 0 else (pos - neg) / (pos + neg))
        return out


@lru_cache
def default_scorer() -> Scorer:
    try:
        import transformers  # noqa: F401
    except ImportError:
        return LexiconScorer()
    return FinBertScorer()
