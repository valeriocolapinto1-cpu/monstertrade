"""Client Trading 212 in SOLA LETTURA (Fase 5, passo B).

Usa solo richieste GET: conto e posizioni. Non contiene alcuna funzione per inviare,
modificare o annullare ordini; il passo C richiede il via esplicito dell'utente.

Documentazione: https://docs.trading212.com/api (beta). Limiti: sintesi del conto
1 richiesta ogni 5 secondi, posizioni 1 al secondo, per conto.
"""

import base64
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.data.ratelimit import RateLimiter

BASE_URLS = {
    "live": "https://live.trading212.com/api/v0",
    "demo": "https://demo.trading212.com/api/v0",
}


class BrokerError(Exception):
    """Errore del broker, senza dettagli che possano contenere credenziali."""


@dataclass(frozen=True)
class AccountSummary:
    currency: str
    total: float
    cash: float
    invested: float
    unrealized_pnl: float


@dataclass(frozen=True)
class BrokerPosition:
    ticker: str
    quantity: float
    average_price: float
    current_price: float
    value: float
    unrealized_pnl: float


def _num(data: dict[str, Any], *keys: str) -> float:
    """Primo campo numerico presente tra le chiavi (l'API è in beta e i nomi cambiano)."""
    for key in keys:
        node: Any = data
        for part in key.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, int | float):
            return float(node)
    return 0.0


def parse_summary(payload: object) -> AccountSummary:
    if not isinstance(payload, dict):
        raise BrokerError("risposta inattesa per il conto")
    return AccountSummary(
        currency=str(payload.get("currency", payload.get("currencyCode", "EUR"))),
        total=_num(payload, "totalValue", "total"),
        cash=_num(payload, "cash.availableToTrade", "cash.free", "free", "cash"),
        invested=_num(payload, "investments.currentValue", "invested"),
        unrealized_pnl=_num(payload, "investments.unrealizedProfitLoss", "ppl"),
    )


def parse_positions(payload: object) -> list[BrokerPosition]:
    if not isinstance(payload, list):
        raise BrokerError("risposta inattesa per le posizioni")
    out: list[BrokerPosition] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        raw_instrument = row.get("instrument")
        instrument: dict[str, Any] = raw_instrument if isinstance(raw_instrument, dict) else {}
        ticker = str(row.get("ticker") or instrument.get("ticker") or "")
        quantity = _num(row, "quantity")
        current = _num(row, "currentPrice")
        out.append(
            BrokerPosition(
                ticker=ticker,
                quantity=quantity,
                average_price=_num(row, "averagePrice", "averagePricePaid"),
                current_price=current,
                value=_num(row, "walletImpact.currentValue") or quantity * current,
                unrealized_pnl=_num(row, "walletImpact.unrealizedProfitLoss", "ppl"),
            )
        )
    return out


class Trading212ReadOnly:
    def __init__(
        self, client: httpx.Client, api_key: str, api_secret: str, env: str = "live"
    ) -> None:
        if env not in BASE_URLS:
            raise ValueError("ambiente Trading 212 non valido")
        token = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
        self._headers = {"Authorization": f"Basic {token}"}
        self._client = client
        self.base_url = BASE_URLS[env]
        self.env = env
        self._limits = {
            "/equity/account/summary": RateLimiter(capacity=1, per_seconds=5),
            "/equity/positions": RateLimiter(capacity=1, per_seconds=1),
        }

    def _get(self, path: str) -> object:
        self._limits[path].acquire()
        try:
            response = self._client.get(f"{self.base_url}{path}", headers=self._headers, timeout=15)
        except httpx.HTTPError:
            raise BrokerError("Trading 212 non raggiungibile") from None
        if response.status_code in (401, 403):
            raise BrokerError("Chiave Trading 212 non valida o senza permessi di lettura")
        if response.status_code == 429:
            raise BrokerError("Troppe richieste a Trading 212: riprova tra poco")
        if response.status_code >= 400:
            raise BrokerError(f"Errore Trading 212 ({response.status_code})")
        try:
            return response.json()
        except ValueError:
            raise BrokerError("Risposta di Trading 212 non leggibile") from None

    def account_summary(self) -> AccountSummary:
        return parse_summary(self._get("/equity/account/summary"))

    def positions(self) -> list[BrokerPosition]:
        return parse_positions(self._get("/equity/positions"))


@dataclass
class BrokerSnapshot:
    fetched_at: float
    summary: AccountSummary
    positions: list[BrokerPosition]


class CachedBroker:
    """Rispetta i limiti di Trading 212 servendo l'ultima lettura per `ttl` secondi."""

    def __init__(self, broker: Trading212ReadOnly, ttl: float = 30.0) -> None:
        self.broker = broker
        self.ttl = ttl
        self._snapshot: BrokerSnapshot | None = None

    def snapshot(self) -> BrokerSnapshot:
        now = time.monotonic()
        if self._snapshot is None or now - self._snapshot.fetched_at > self.ttl:
            self._snapshot = BrokerSnapshot(
                now, self.broker.account_summary(), self.broker.positions()
            )
        return self._snapshot
