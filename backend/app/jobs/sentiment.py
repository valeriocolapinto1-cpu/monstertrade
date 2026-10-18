"""Raccolta del sentiment: notizie, StockTwits, Fear and Greed (e Finnhub/Reddit con chiavi).

Uso:  python -m app.jobs.sentiment [--history]
      --history scarica tutto lo storico del Fear and Greed (dal 2018) per il backtest.
"""

import argparse
import logging

import httpx
from sqlalchemy import Engine

from app.config import get_settings
from app.data.sources.base import SourceError
from app.db import repository as repo
from app.db.engine import get_engine
from app.sentiment.aggregate import daily, score_items
from app.sentiment.scorer import Scorer, default_scorer
from app.sentiment.sources import (
    TARGETS,
    FearGreedSource,
    FinnhubSource,
    GoogleNewsSource,
    Item,
    RedditSource,
    SentimentSource,
    StockTwitsSource,
)

log = logging.getLogger("jobs.sentiment")


def build_sources(client: httpx.Client, history: bool) -> list[SentimentSource]:
    s = get_settings()

    def secret(v: object) -> str | None:
        return v.get_secret_value() if v is not None else None  # type: ignore[attr-defined]

    return [
        GoogleNewsSource(client),
        StockTwitsSource(client),
        FearGreedSource(client, days=0 if history else 30),
        FinnhubSource(client, secret(s.finnhub_api_key)),
        RedditSource(client, secret(s.reddit_client_id), secret(s.reddit_client_secret)),
    ]


def run(engine: Engine, sources: list[SentimentSource], scorer: Scorer) -> int:
    items: list[Item] = []
    for target in TARGETS:
        for source in sources:
            if not source.available():
                continue
            try:
                items.extend(source.fetch(target))
            except SourceError as exc:
                log.warning("sentiment: %s", exc)
    scores = score_items(items, scorer)
    rows = daily(items, scores)
    with engine.begin() as conn:
        ids = repo.instrument_ids(conn)
        payload: list[dict[str, object]] = [
            {
                "instrument_id": ids[r.symbol],
                "date": r.day,
                "source": r.source,
                "score": r.score,
                "mentions": r.mentions,
            }
            for r in rows
            if r.symbol in ids
        ]
        count = repo.upsert_sentiment(conn, payload)
    log.info("sentiment: %d testi, %d righe giornaliere (%s)", len(items), count, scorer.name)
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    with httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (monstertrade)"}, follow_redirects=True
    ) as client:
        run(get_engine(), build_sources(client, args.history), default_scorer())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
