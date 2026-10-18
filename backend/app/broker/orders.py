"""Client Trading 212 per gli ORDINI (Fase 5, passo C).

Separato dal client di sola lettura: usa una chiave diversa, con permesso di trading,
e un ambiente (demo o live) scelto da `ORDERS_MODE`. Non ritenta mai una richiesta di
invio: se l'esito è sconosciuto (timeout, errore del server) l'ordine resta "incerto"
e va verificato nell'app di Trading 212.

Endpoint (docs.trading212.com, beta): POST /equity/orders/market e /equity/orders/stop;
la vendita ha quantità negativa; GET /equity/orders elenca gli ordini in attesa.
"""

import base64
from dataclasses import dataclass
from typing import Any

import httpx

from app.broker.trading212 import (
    BASE_URLS,
    AccountSummary,
    BrokerError,
    BrokerPosition,
    parse_positions,
    parse_summary,
)
from app.data.ratelimit import RateLimiter


class OrderRejectedError(BrokerError):
    """L'ordine non è stato accettato: nessuna esecuzione."""


class OrderUncertainError(BrokerError):
    """Esito sconosciuto: l'ordine potrebbe essere stato eseguito. Nessun nuovo tentativo."""


@dataclass(frozen=True)
class PlacedOrder:
    order_id: str
    status: str
    filled_quantity: float
    fill_price: float | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class PendingOrder:
    order_id: str
    ticker: str
    type: str
    quantity: float


def _safe_error(response: httpx.Response) -> str:
    """Solo il codice d'errore del broker, mai il corpo completo o le intestazioni."""
    try:
        body = response.json()
    except ValueError:
        body = None
    code = ""
    if isinstance(body, dict):
        for key in ("code", "errorCode", "type", "clarification"):
            value = body.get(key)
            if isinstance(value, str) and value:
                code = value[:120]
                break
    suffix = f": {code}" if code else ""
    return f"Ordine rifiutato da Trading 212 ({response.status_code}){suffix}"


def _float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def parse_order(payload: object) -> PlacedOrder:
    if not isinstance(payload, dict) or payload.get("id") is None:
        raise OrderUncertainError("Risposta di Trading 212 senza identificativo dell'ordine")
    filled = _float(payload.get("filledQuantity")) or 0.0
    price = _float(payload.get("fillPrice"))
    value = _float(payload.get("filledValue"))
    if price is None and value and filled:
        price = value / filled
    return PlacedOrder(
        order_id=str(payload["id"]),
        status=str(payload.get("status", "")),
        filled_quantity=filled,
        fill_price=price,
        raw={k: v for k, v in payload.items() if isinstance(v, str | int | float | bool)},
    )


def parse_pending(payload: object) -> list[PendingOrder]:
    if not isinstance(payload, list):
        raise BrokerError("risposta inattesa per gli ordini in attesa")
    out: list[PendingOrder] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        instrument = row.get("instrument")
        ticker = row.get("ticker") or (
            instrument.get("ticker") if isinstance(instrument, dict) else ""
        )
        out.append(
            PendingOrder(
                order_id=str(row.get("id", "")),
                ticker=str(ticker or ""),
                type=str(row.get("type", "")),
                quantity=_float(row.get("quantity")) or 0.0,
            )
        )
    return out


class Trading212Orders:
    def __init__(self, client: httpx.Client, api_key: str, api_secret: str, env: str) -> None:
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
            "/equity/orders": RateLimiter(capacity=1, per_seconds=5),
            "/equity/metadata/instruments": RateLimiter(capacity=1, per_seconds=50),
            "/equity/orders/market": RateLimiter(capacity=1, per_seconds=2),
            "/equity/orders/stop": RateLimiter(capacity=1, per_seconds=2),
        }

    # --- Letture ----------------------------------------------------------------

    def _get(self, path: str) -> object:
        self._limits[path].acquire()
        try:
            response = self._client.get(f"{self.base_url}{path}", headers=self._headers, timeout=15)
        except httpx.HTTPError:
            raise BrokerError("Trading 212 non raggiungibile") from None
        if response.status_code in (401, 403):
            raise BrokerError("Chiave ordini Trading 212 non valida o senza permessi")
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

    def pending_orders(self) -> list[PendingOrder]:
        return parse_pending(self._get("/equity/orders"))

    def instruments(self) -> list[dict[str, Any]]:
        payload = self._get("/equity/metadata/instruments")
        if not isinstance(payload, list):
            raise BrokerError("risposta inattesa per gli strumenti")
        return [row for row in payload if isinstance(row, dict)]

    # --- Invio (mai ritentato) ----------------------------------------------------

    def _post(self, path: str, body: dict[str, Any]) -> PlacedOrder:
        self._limits[path].acquire()
        try:
            response = self._client.post(
                f"{self.base_url}{path}", headers=self._headers, json=body, timeout=20
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # La connessione non è mai partita: l'ordine non è arrivato al broker.
            raise OrderRejectedError("Trading 212 non raggiungibile: ordine non inviato") from None
        except httpx.HTTPError:
            raise OrderUncertainError(
                "Nessuna risposta da Trading 212: verifica l'ordine nell'app"
            ) from None
        if response.status_code >= 500:
            raise OrderUncertainError(
                f"Errore del server Trading 212 ({response.status_code}): verifica nell'app"
            )
        if response.status_code >= 400:
            raise OrderRejectedError(_safe_error(response))
        try:
            return parse_order(response.json())
        except ValueError:
            raise OrderUncertainError("Risposta di Trading 212 non leggibile") from None

    def place_market(self, ticker: str, quantity: float) -> PlacedOrder:
        if quantity <= 0:
            raise ValueError("la quantità di acquisto deve essere positiva")
        return self._post("/equity/orders/market", {"ticker": ticker, "quantity": quantity})

    def place_stop(self, ticker: str, quantity: float, stop_price: float) -> PlacedOrder:
        """Stop di protezione: vendita (quantità negativa) valida fino a revoca."""
        if quantity <= 0 or stop_price <= 0:
            raise ValueError("quantità e prezzo di stop devono essere positivi")
        return self._post(
            "/equity/orders/stop",
            {
                "ticker": ticker,
                "quantity": -quantity,
                "stopPrice": stop_price,
                "timeValidity": "GOOD_TILL_CANCEL",
            },
        )
