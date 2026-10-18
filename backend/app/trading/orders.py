"""Ordini reali con conferma (Fase 5, passo C).

Flusso obbligato, senza scorciatoie:

1. `preview`: tutti i controlli, quantità stimata e un codice di conferma valido
   `CONFIRM_TTL` secondi, legato a proposta, quantità e modalità.
2. `place`: solo con quel codice (il tocco di conferma dell'utente). I controlli si
   ripetono, la riga del registro si scrive PRIMA dell'invio, poi ordine a mercato e
   stop di protezione. Nessun nuovo tentativo automatico.

Blocchi: `ORDERS_MODE=disabled` (predefinito), blocco totale (attivo se mai disattivato),
limiti per ordine e per giorno, perdita giornaliera, limiti di rischio del piano.
"""

import hashlib
import hmac
import math
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import httpx
from sqlalchemy import Connection, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.analysis.costs import cost_model
from app.broker.orders import (
    OrderRejectedError,
    OrderUncertainError,
    PlacedOrder,
    Trading212Orders,
)
from app.broker.quotes import Quote, yahoo_quote
from app.broker.service import real_state
from app.broker.trading212 import BrokerError, BrokerSnapshot
from app.config import Settings, get_settings
from app.data.universe import BY_SYMBOL, InstrumentSpec
from app.db.schema import controls, instruments, orders, trade_ideas
from app.trading import engine
from app.trading.risk import (
    ATR_STOP,
    Rejection,
    TradeRequest,
    daily_limit_reached,
    plan_trade,
)

CONFIRM_TTL = 90
KILL_SWITCH = "kill_switch"
# Chiave dei codici di conferma: nuova a ogni avvio, mai salvata né mostrata.
_CONFIRM_KEY = secrets.token_bytes(32)
# Suffisso di borsa del ticker Trading 212 per il simbolo Yahoo (".L" Londra, ".PA" Parigi).
_EXCHANGE_SUFFIX = {".L": "l_EQ", ".PA": "p_EQ"}

QuoteFn = Callable[[str], Quote]


class OrderBlockedError(Exception):
    """Ordine non consentito: il motivo è mostrato all'utente così com'è."""


@lru_cache
def get_order_broker() -> Trading212Orders | None:
    s = get_settings()
    if s.orders_mode == "disabled":
        return None
    if s.t212_order_api_key is None or s.t212_order_api_secret is None:
        return None
    return Trading212Orders(
        httpx.Client(headers={"User-Agent": "monstertrade/0.1"}),
        s.t212_order_api_key.get_secret_value(),
        s.t212_order_api_secret.get_secret_value(),
        s.orders_mode,
    )


# --- Blocco totale ----------------------------------------------------------------


def kill_switch_active(conn: Connection) -> bool:
    value = conn.execute(select(controls.c.active).where(controls.c.key == KILL_SWITCH)).scalar()
    return True if value is None else bool(value)


def set_kill_switch(conn: Connection, active: bool) -> None:
    conn.execute(
        insert(controls)
        .values(key=KILL_SWITCH, active=active)
        .on_conflict_do_update(
            index_elements=[controls.c.key], set_={"active": active, "updated_at": func.now()}
        )
    )


# --- Codice di conferma -------------------------------------------------------------


def _digest(idea_id: int, quantity: float, mode: str, expires: int) -> str:
    message = f"{idea_id}|{quantity:.6f}|{mode}|{expires}".encode()
    return hmac.new(_CONFIRM_KEY, message, hashlib.sha256).hexdigest()


def confirm_token(idea_id: int, quantity: float, mode: str, now: float | None = None) -> str:
    expires = int((time.time() if now is None else now) + CONFIRM_TTL)
    return f"{expires}.{_digest(idea_id, quantity, mode, expires)}"


def token_valid(
    token: str, idea_id: int, quantity: float, mode: str, now: float | None = None
) -> bool:
    expires_raw, _, digest = token.partition(".")
    if not expires_raw.isdigit() or not digest:
        return False
    expires = int(expires_raw)
    if expires < (time.time() if now is None else now):
        return False
    return hmac.compare_digest(digest, _digest(idea_id, quantity, mode, expires))


# --- Controlli ----------------------------------------------------------------------


@dataclass(frozen=True)
class Prepared:
    idea_id: int
    spec: InstrumentSpec
    ticker: str
    horizon: str
    stop_pct: float
    quantity: float
    quote: Quote
    max_eur: float
    risk_eur: float

    @property
    def estimated_eur(self) -> float:
        return round(self.quantity * self.quote.eur_per_unit, 2)


def orders_today(conn: Connection, mode: str) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        conn.execute(
            select(func.count())
            .select_from(orders)
            .where(
                orders.c.mode == mode,
                orders.c.created_at >= start,
                orders.c.status != "rifiutato",
            )
        ).scalar_one()
    )


def resolve_ticker(conn: Connection, broker: Trading212Orders, spec: InstrumentSpec) -> str:
    """Ticker Trading 212 dello strumento: dal database o, la prima volta, dai metadati."""
    saved = conn.execute(
        select(instruments.c.t212_ticker).where(instruments.c.symbol == spec.symbol)
    ).scalar()
    if saved:
        return str(saved)
    ref = (spec.reference_ticker or "").upper()
    suffix = next(
        (v for k, v in _EXCHANGE_SUFFIX.items() if (spec.quote_symbol or "").endswith(k)), ""
    )
    candidates = [
        str(row.get("ticker"))
        for row in broker.instruments()
        if str(row.get("shortName", "")).upper() == ref and row.get("ticker")
    ]
    preferred = [t for t in candidates if suffix and t.endswith(suffix)]
    chosen = next(iter(preferred or candidates), None)
    if chosen is None:
        raise OrderBlockedError(
            f"{spec.reference_ticker} non trovato tra gli strumenti Trading 212"
        )
    conn.execute(
        update(instruments).where(instruments.c.symbol == spec.symbol).values(t212_ticker=chosen)
    )
    return chosen


def _snapshot(broker: Trading212Orders) -> BrokerSnapshot:
    return BrokerSnapshot(time.monotonic(), broker.account_summary(), broker.positions())


def _round_price(value: float) -> float:
    return round(value, 2 if value >= 10 else 4)


def prepare(
    conn: Connection,
    idea_id: int,
    settings: Settings | None = None,
    broker: Trading212Orders | None = None,
    quote_fn: QuoteFn | None = None,
) -> Prepared:
    s = settings or get_settings()
    if s.orders_mode == "disabled":
        raise OrderBlockedError("Ordini disattivati (ORDERS_MODE=disabled)")
    broker = broker or get_order_broker()
    if broker is None:
        raise OrderBlockedError("Chiave Trading 212 per gli ordini non configurata")
    if broker.env != s.orders_mode:
        raise OrderBlockedError("Ambiente del broker diverso da ORDERS_MODE")
    if kill_switch_active(conn):
        raise OrderBlockedError("Blocco totale attivo: nessun ordine possibile")

    idea = (
        conn.execute(
            select(trade_ideas, instruments.c.symbol)
            .join(instruments, instruments.c.id == trade_ideas.c.instrument_id)
            .where(trade_ideas.c.id == idea_id)
        )
        .mappings()
        .first()
    )
    if idea is None:
        raise OrderBlockedError("Proposta inesistente")
    if idea["status"] != "proposta":
        raise OrderBlockedError("La proposta non è più attiva")
    if idea["expires_at"] <= datetime.now(UTC):
        raise OrderBlockedError("Proposta scaduta")
    existing = conn.execute(
        select(orders.c.id).where(orders.c.idea_id == idea_id, orders.c.status != "rifiutato")
    ).first()
    if existing is not None:
        raise OrderBlockedError("Ordine già inviato per questa proposta")
    spec = BY_SYMBOL.get(str(idea["symbol"]))
    if spec is None or not spec.orderable:
        raise OrderBlockedError("Strumento non ordinabile tramite Trading 212 Invest")
    if orders_today(conn, s.orders_mode) >= s.max_orders_per_day:
        raise OrderBlockedError(f"Limite di {s.max_orders_per_day} ordini al giorno raggiunto")

    cfg = engine.risk_config(s)
    try:
        state = real_state(conn, _snapshot(broker), s.orders_mode)
    except BrokerError as exc:
        raise OrderBlockedError(str(exc)) from None
    if daily_limit_reached(state, cfg):
        raise OrderBlockedError("Perdita giornaliera massima raggiunta: ordini bloccati")

    # Si ripetono tutti i limiti del piano sul conto attuale, con lo stesso stop.
    stop_pct = 1 - float(idea["stop"]) / float(idea["entry"])
    horizon = str(idea["horizon"])
    holding = [p.symbol for p in state.open_positions]
    plan = plan_trade(
        TradeRequest(
            spec.symbol,
            horizon,
            spec.leverage,
            float(idea["entry"]),
            stop_pct * 100 / ATR_STOP[horizon],
            cost_model(spec).round_trip,
            engine.correlations(conn, spec.symbol, holding),
        ),
        state,
        cfg,
    )
    if isinstance(plan, Rejection):
        raise OrderBlockedError(plan.reason)
    max_eur = min(plan.size_eur, s.max_order_eur)

    ticker = resolve_ticker(conn, broker, spec)
    try:
        pending = broker.pending_orders()
    except BrokerError as exc:
        raise OrderBlockedError(str(exc)) from None
    if any(o.ticker == ticker and o.type.upper() != "STOP" for o in pending):
        raise OrderBlockedError("C'è già un ordine in attesa su questo strumento")

    try:
        quote = (quote_fn or yahoo_quote)(str(spec.quote_symbol))
    except BrokerError as exc:
        raise OrderBlockedError(str(exc)) from None
    quantity = math.floor(max_eur / quote.eur_per_unit * 100) / 100
    if quantity <= 0 or quantity * quote.eur_per_unit < cfg.min_order:
        raise OrderBlockedError("Importo sotto il minimo acquistabile con i limiti attuali")
    return Prepared(
        idea_id=idea_id,
        spec=spec,
        ticker=ticker,
        horizon=horizon,
        stop_pct=stop_pct,
        quantity=quantity,
        quote=quote,
        max_eur=max_eur,
        risk_eur=round(quantity * quote.eur_per_unit * (stop_pct + cost_model(spec).round_trip), 2),
    )


def preview(
    conn: Connection,
    idea_id: int,
    settings: Settings | None = None,
    broker: Trading212Orders | None = None,
    quote_fn: QuoteFn | None = None,
) -> dict[str, object]:
    s = settings or get_settings()
    p = prepare(conn, idea_id, s, broker, quote_fn)
    conn.commit()  # ticker risolto e valore di inizio giornata
    return {
        "idea_id": idea_id,
        "mode": s.orders_mode,
        "symbol": p.spec.symbol,
        "name": p.spec.name,
        "ticker": p.ticker,
        "quantity": p.quantity,
        "price": p.quote.price,
        "currency": p.quote.currency,
        "estimated_eur": p.estimated_eur,
        "stop_pct": round(p.stop_pct, 6),
        "stop_price": _round_price(p.quote.price * (1 - p.stop_pct)),
        "risk_eur": p.risk_eur,
        "max_order_eur": s.max_order_eur,
        "token": confirm_token(idea_id, p.quantity, s.orders_mode),
        "expires_in": CONFIRM_TTL,
    }


# --- Invio ----------------------------------------------------------------------------


def _fill_reference(broker: Trading212Orders, ticker: str, placed: PlacedOrder) -> float | None:
    """Prezzo di carico dalla risposta o dalla posizione (poche letture, senza insistere)."""
    if placed.fill_price:
        return placed.fill_price
    for _ in range(3):
        try:
            for pos in broker.positions():
                if pos.ticker == ticker and pos.average_price > 0:
                    return pos.average_price
        except BrokerError:
            return None
    return None


def _update(conn: Connection, order_id: int, **values: Any) -> None:
    conn.execute(
        update(orders).where(orders.c.id == order_id).values(updated_at=func.now(), **values)
    )
    conn.commit()


def place(
    conn: Connection,
    idea_id: int,
    quantity: float,
    token: str,
    settings: Settings | None = None,
    broker: Trading212Orders | None = None,
    quote_fn: QuoteFn | None = None,
) -> dict[str, object]:
    s = settings or get_settings()
    # Prima di tutto la conferma: senza il codice mostrato all'utente non si procede.
    if not token_valid(token, idea_id, quantity, s.orders_mode):
        raise OrderBlockedError("Conferma mancante, scaduta o non corrispondente: riapri l'ordine")
    broker = broker or get_order_broker()
    if broker is None:
        raise OrderBlockedError("Chiave Trading 212 per gli ordini non configurata")
    p = prepare(conn, idea_id, s, broker, quote_fn)
    if quantity > p.quantity * 1.02 or quantity * p.quote.eur_per_unit > s.max_order_eur:
        raise OrderBlockedError("Quantità oltre i limiti attuali: riapri l'ordine")

    request = {"ticker": p.ticker, "quantity": quantity, "type": "MARKET"}
    try:
        # Un solo ordine alla volta, così il conteggio giornaliero non si supera.
        conn.execute(text("SELECT pg_advisory_xact_lock(212)"))
        if orders_today(conn, s.orders_mode) >= s.max_orders_per_day:
            raise OrderBlockedError(f"Limite di {s.max_orders_per_day} ordini al giorno raggiunto")
        order_id = int(
            conn.execute(
                insert(orders)
                .values(
                    idea_id=idea_id,
                    mode=s.orders_mode,
                    ticker=p.ticker,
                    quantity=quantity,
                    estimated_eur=round(quantity * p.quote.eur_per_unit, 2),
                    stop_pct=p.stop_pct,
                    request=request,
                )
                .returning(orders.c.id)
            ).scalar_one()
        )
        conn.commit()  # registro scritto prima dell'invio
    except IntegrityError:
        conn.rollback()
        raise OrderBlockedError("Ordine già inviato per questa proposta") from None

    try:
        placed = broker.place_market(p.ticker, quantity)
    except OrderRejectedError as exc:
        _update(conn, order_id, status="rifiutato", error=str(exc))
        return order_row(conn, order_id)
    except OrderUncertainError as exc:
        _update(conn, order_id, status="incerto", error=str(exc))
        return order_row(conn, order_id)
    _update(conn, order_id, status="inviato", broker_order_id=placed.order_id, response=placed.raw)

    fill = _fill_reference(broker, p.ticker, placed)
    status = "eseguito" if fill else "inviato"
    reference = fill or p.quote.price
    stop_price = _round_price(reference * (1 - p.stop_pct))
    stop_qty = placed.filled_quantity or quantity
    try:
        stop = broker.place_stop(p.ticker, stop_qty, stop_price)
        _update(
            conn,
            order_id,
            status=status,
            fill_price=fill,
            stop_status="attivo",
            stop_price=stop_price,
            stop_order_id=stop.order_id,
        )
    except BrokerError as exc:
        _update(
            conn,
            order_id,
            status=status,
            fill_price=fill,
            stop_status="da_impostare",
            stop_price=stop_price,
            error=f"Stop NON impostato, impostalo a mano a {stop_price}: {exc}",
        )
    return order_row(conn, order_id)


def _serialize(row: Any) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in dict(row).items():
        out[key] = value.isoformat() if isinstance(value, datetime) else value
    return out


def order_row(conn: Connection, order_id: int) -> dict[str, object]:
    row = conn.execute(select(orders).where(orders.c.id == order_id)).mappings().one()
    return _serialize(row)


def recent_orders(conn: Connection, limit: int = 50) -> list[dict[str, object]]:
    rows = (
        conn.execute(
            select(orders, instruments.c.symbol)
            .join(trade_ideas, trade_ideas.c.id == orders.c.idea_id)
            .join(instruments, instruments.c.id == trade_ideas.c.instrument_id)
            .order_by(orders.c.id.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    return [
        {k: v for k, v in _serialize(r).items() if k not in ("request", "response")} for r in rows
    ]
