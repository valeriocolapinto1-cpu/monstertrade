from datetime import UTC, datetime

import httpx
import pytest

from app.data.sources.base import SourceError, SourceUnavailableError
from app.sentiment.aggregate import daily, score_items
from app.sentiment.scorer import LexiconScorer, _finbert_to_score
from app.sentiment.sources import (
    FinnhubSource,
    Item,
    RedditSource,
    Target,
    parse_fear_greed,
    parse_rss,
    parse_stocktwits,
)

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Nasdaq rallies on chip rebound - Reuters</title>
<pubDate>Fri, 16 Oct 2026 14:00:00 GMT</pubDate></item>
<item><title>Senza data</title></item>
</channel></rss>"""


def test_parse_rss_strips_publisher_and_skips_incomplete() -> None:
    items = parse_rss(RSS, "NDX", "news")
    assert len(items) == 1
    assert items[0].text == "Nasdaq rallies on chip rebound"
    assert items[0].ts == datetime(2026, 10, 16, 14, tzinfo=UTC)


def test_parse_rss_rejects_xml_bombs_and_garbage() -> None:
    bomb = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss>&a;</rss>'
    with pytest.raises(SourceError):  # defusedxml blocca le entità
        parse_rss(bomb, "NDX", "news")
    with pytest.raises(SourceError):
        parse_rss("non è xml", "NDX", "news")


def test_parse_stocktwits_uses_user_tags() -> None:
    payload = {
        "messages": [
            {
                "body": "to the moon",
                "created_at": "2026-10-18T04:06:35Z",
                "entities": {"sentiment": {"basic": "Bullish"}},
            },
            {"body": "meh", "created_at": "2026-10-18T04:07:00Z", "entities": {"sentiment": None}},
            {"body": "", "created_at": "2026-10-18T04:07:00Z"},
        ]
    }
    items = parse_stocktwits(payload, "NDX")
    assert [i.value for i in items] == [1.0, None]


def test_parse_fear_greed_maps_to_unit_range() -> None:
    items = parse_fear_greed(
        {
            "data": [
                {"value": "25", "timestamp": "1792281600"},
                {"value": "100", "timestamp": "1792195200"},
            ]
        },
        "BTC",
    )
    assert [i.value for i in items] == [-0.5, 1.0]


def test_keyed_sources_are_inactive_without_credentials() -> None:
    client = httpx.Client()
    assert not FinnhubSource(client, None).available()
    assert not RedditSource(client, None, None).available()
    with pytest.raises(SourceUnavailableError):
        FinnhubSource(client, None).fetch(Target("SPX", "x", finnhub="SPY"))


def test_finnhub_errors_do_not_leak_key() -> None:
    key = "-".join(["finto", "token", "di", "prova"])
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(SourceError) as info:
        FinnhubSource(client, key).fetch(Target("SPX", "x", finnhub="SPY"))
    assert key not in str(info.value)


def test_lexicon_and_finbert_mapping() -> None:
    assert LexiconScorer().score(["Stocks surge to record", "Shares plunge", "Fed meets"]) == [
        1.0,
        -1.0,
        0.0,
    ]
    probs = [
        {"label": "positive", "score": 0.7},
        {"label": "negative", "score": 0.2},
        {"label": "neutral", "score": 0.1},
    ]
    assert _finbert_to_score(probs) == pytest.approx(0.5)


class CountingScorer:
    name = "prova"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def score(self, texts: list[str]) -> list[float]:
        self.seen.extend(texts)
        return [0.4 for _ in texts]


def test_scores_only_untagged_texts_and_aggregates_by_day() -> None:
    t = datetime(2026, 10, 16, 10, tzinfo=UTC)
    items = [
        Item("stocktwits", "NDX", t, "bull", 1.0),
        Item("stocktwits", "NDX", t, "testo libero"),
        Item("news", "NDX", t, "titolo"),
        Item("feargreed", "BTC", t, "", -0.2),
    ]
    scorer = CountingScorer()
    scores = score_items(items, scorer)
    assert scorer.seen == ["testo libero", "titolo"]
    rows = {(r.symbol, r.source): r for r in daily(items, scores)}
    assert rows[("NDX", "stocktwits")].score == pytest.approx(0.7)
    assert rows[("NDX", "stocktwits")].mentions == 2
    assert rows[("BTC", "feargreed")].score == pytest.approx(-0.2)
