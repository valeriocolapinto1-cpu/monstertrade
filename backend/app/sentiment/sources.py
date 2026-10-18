"""Fonti di sentiment, ognuna dietro la stessa interfaccia.

Senza chiavi: Google News RSS, StockTwits (API pubblica), Alternative.me Fear and Greed.
Con chiavi: Finnhub (FINNHUB_API_KEY), Reddit (REDDIT_CLIENT_ID e REDDIT_CLIENT_SECRET).
Niente X/Twitter.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

import httpx
from defusedxml import DefusedXmlException, ElementTree

from app.data.ratelimit import RateLimiter
from app.data.sources.base import SourceError, SourceUnavailableError


@dataclass(frozen=True)
class Item:
    """Un testo (o un indice già numerico) riferito a uno strumento."""

    source: str
    symbol: str
    ts: datetime
    text: str = ""
    # Valore già disponibile in [-1, 1] (etichetta utente o indice): FinBERT non serve.
    value: float | None = None


@dataclass(frozen=True)
class Target:
    """Come cercare il sentiment di uno strumento di base."""

    symbol: str
    news_query: str
    stocktwits: str | None = None
    finnhub: str | None = None
    reddit: tuple[str, ...] = ()
    fear_greed: bool = False


TARGETS: tuple[Target, ...] = (
    Target("SPX", '"S&P 500" stocks', "SPY", "SPY", ("investing", "stocks")),
    Target("NDX", '"Nasdaq 100" OR "Nasdaq" tech stocks', "QQQ", "QQQ", ("wallstreetbets",)),
    Target("SOX", "semiconductor stocks", "SOXX", "SOXX", ("semiconductors",)),
    Target("BTC", "bitcoin", "BTC.X", None, ("CryptoCurrency", "Bitcoin"), fear_greed=True),
    Target("ETH", "ethereum", "ETH.X", None, ("CryptoCurrency", "ethereum"), fear_greed=True),
    Target("SOL", "solana crypto", "SOL.X", None, ("CryptoCurrency", "solana"), fear_greed=True),
)


class SentimentSource(Protocol):
    name: str

    def available(self) -> bool: ...

    def fetch(self, target: Target) -> list[Item]: ...


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class GoogleNewsSource:
    name = "news"

    def __init__(self, client: httpx.Client, limiter: RateLimiter | None = None) -> None:
        self.client = client
        self.limiter = limiter or RateLimiter(capacity=1, per_seconds=2)

    def available(self) -> bool:
        return True

    def fetch(self, target: Target) -> list[Item]:
        self.limiter.acquire()
        try:
            response = self.client.get(
                "https://news.google.com/rss/search",
                params={
                    "q": f"{target.news_query} when:3d",
                    "hl": "en-US",
                    "gl": "US",
                    "ceid": "US:en",
                },
                timeout=20,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SourceError(f"news {target.symbol}: {exc}") from exc
        return parse_rss(response.text, target.symbol, self.name)


def parse_rss(xml: str, symbol: str, source: str) -> list[Item]:
    try:
        root = ElementTree.fromstring(xml)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        # Le entità XML (possibili "XML bomb") sono rifiutate da defusedxml.
        raise SourceError(f"{source} {symbol}: RSS non valido") from exc
    items: list[Item] = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        published = node.findtext("pubDate")
        if not title or not published:
            continue
        # Google aggiunge " - Testata" in coda al titolo.
        headline = title.rsplit(" - ", 1)[0] if " - " in title else title
        items.append(Item(source, symbol, _utc(parsedate_to_datetime(published)), headline))
    return items


class StockTwitsSource:
    name = "stocktwits"

    def __init__(self, client: httpx.Client, limiter: RateLimiter | None = None) -> None:
        self.client = client
        self.limiter = limiter or RateLimiter(capacity=1, per_seconds=4)

    def available(self) -> bool:
        return True

    def fetch(self, target: Target) -> list[Item]:
        if not target.stocktwits:
            return []
        self.limiter.acquire()
        try:
            response = self.client.get(
                f"https://api.stocktwits.com/api/2/streams/symbol/{target.stocktwits}.json",
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SourceError(f"stocktwits {target.symbol}: {exc}") from exc
        return parse_stocktwits(payload, target.symbol)


def parse_stocktwits(payload: object, symbol: str) -> list[Item]:
    if not isinstance(payload, dict):
        raise SourceError(f"stocktwits {symbol}: risposta inattesa")
    items: list[Item] = []
    for msg in payload.get("messages", []):
        body = str(msg.get("body", "")).strip()
        created = msg.get("created_at")
        if not body or not created:
            continue
        tag = ((msg.get("entities") or {}).get("sentiment") or {}).get("basic")
        value = 1.0 if tag == "Bullish" else -1.0 if tag == "Bearish" else None
        ts = _utc(datetime.fromisoformat(str(created).replace("Z", "+00:00")))
        items.append(Item("stocktwits", symbol, ts, body, value))
    return items


class FearGreedSource:
    """Indice giornaliero 0-100 convertito in [-1, 1]; storico disponibile dal 2018."""

    name = "feargreed"

    def __init__(self, client: httpx.Client, days: int = 30) -> None:
        # days = 0: tutto lo storico disponibile.
        self.client = client
        self.days = days

    def available(self) -> bool:
        return True

    def fetch(self, target: Target) -> list[Item]:
        if not target.fear_greed:
            return []
        try:
            response = self.client.get(
                "https://api.alternative.me/fng/", params={"limit": self.days}, timeout=20
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SourceError(f"feargreed: {exc}") from exc
        return parse_fear_greed(payload, target.symbol)


def parse_fear_greed(payload: object, symbol: str) -> list[Item]:
    if not isinstance(payload, dict):
        raise SourceError("feargreed: risposta inattesa")
    items = []
    for row in payload.get("data", []):
        value = (float(row["value"]) - 50) / 50
        ts = datetime.fromtimestamp(int(row["timestamp"]), tz=UTC)
        items.append(Item("feargreed", symbol, ts, "", value))
    return items


class FinnhubSource:
    name = "finnhub"

    def __init__(self, client: httpx.Client, api_key: str | None) -> None:
        self.client = client
        self._key = api_key
        self.limiter = RateLimiter(capacity=30, per_seconds=60)

    def available(self) -> bool:
        return bool(self._key)

    def fetch(self, target: Target) -> list[Item]:
        if not self._key:
            raise SourceUnavailableError("FINNHUB_API_KEY non impostata")
        if not target.finnhub:
            return []
        today = datetime.now(UTC).date()
        self.limiter.acquire()
        try:
            response = self.client.get(
                "https://finnhub.io/api/v1/company-news",
                params={
                    "symbol": target.finnhub,
                    "from": str(today.replace(day=1)),
                    "to": str(today),
                },
                headers={"X-Finnhub-Token": self._key},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            raise SourceError(f"finnhub {target.symbol}: errore di rete") from None
        return [
            Item(
                "finnhub",
                target.symbol,
                datetime.fromtimestamp(int(n["datetime"]), tz=UTC),
                str(n.get("headline", "")),
            )
            for n in payload
            if isinstance(n, dict) and n.get("headline")
        ]


class RedditSource:
    """API ufficiale con OAuth (app approvata): titoli dei post recenti."""

    name = "reddit"

    def __init__(self, client: httpx.Client, client_id: str | None, secret: str | None) -> None:
        self.client = client
        self._id = client_id
        self._secret = secret
        self._token: str | None = None
        self.limiter = RateLimiter(capacity=60, per_seconds=60)

    def available(self) -> bool:
        return bool(self._id and self._secret)

    def _auth(self) -> str:
        if self._token:
            return self._token
        if not (self._id and self._secret):
            raise SourceUnavailableError("credenziali Reddit non impostate")
        try:
            response = self.client.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(self._id, self._secret),
                headers={"User-Agent": "monstertrade/0.1"},
                timeout=20,
            )
            response.raise_for_status()
            self._token = str(response.json()["access_token"])
        except (httpx.HTTPError, ValueError, KeyError):
            raise SourceError("reddit: autenticazione non riuscita") from None
        return self._token

    def fetch(self, target: Target) -> list[Item]:
        token = self._auth()
        items: list[Item] = []
        for sub in target.reddit:
            self.limiter.acquire()
            try:
                response = self.client.get(
                    f"https://oauth.reddit.com/r/{sub}/new",
                    params={"limit": 50},
                    headers={"Authorization": f"Bearer {token}", "User-Agent": "monstertrade/0.1"},
                    timeout=20,
                )
                response.raise_for_status()
                children = response.json()["data"]["children"]
            except (httpx.HTTPError, ValueError, KeyError):
                raise SourceError(f"reddit r/{sub}: errore") from None
            for child in children:
                post = child.get("data", {})
                if post.get("title"):
                    ts = datetime.fromtimestamp(float(post["created_utc"]), tz=UTC)
                    items.append(Item("reddit", target.symbol, ts, str(post["title"])))
        return items
