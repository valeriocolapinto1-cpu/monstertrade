"""Ordini con conferma e blocco totale: le uniche scritture esposte dall'API.

Protette dal segreto condiviso (middleware) e raggiungibili solo dal server del
frontend, che a sua volta richiede la sessione e controlla l'origine.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from app.api.deps import get_conn
from app.config import get_settings
from app.trading import orders as svc
from app.trading.engine import reset_proposals

router = APIRouter(prefix="/api")
Conn = Annotated[Connection, Depends(get_conn)]


class PreviewBody(BaseModel):
    idea_id: int = Field(gt=0)


class PlaceBody(BaseModel):
    idea_id: int = Field(gt=0)
    quantity: float = Field(gt=0, le=1_000_000)
    token: str = Field(min_length=10, max_length=128, pattern=r"^\d+\.[0-9a-f]{64}$")


class KillSwitchBody(BaseModel):
    active: bool


def _blocked(exc: svc.OrderBlockedError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/orders")
def list_orders(conn: Conn) -> dict[str, object]:
    s = get_settings()
    configured = svc.get_order_broker() is not None
    return {
        "mode": s.orders_mode,
        "configured": configured,
        "kill_switch": svc.kill_switch_active(conn),
        "limits": {
            "max_order_eur": s.max_order_eur,
            "max_orders_per_day": s.max_orders_per_day,
            "today": svc.orders_today(conn, s.orders_mode) if s.orders_mode != "disabled" else 0,
        },
        "orders": svc.recent_orders(conn),
    }


@router.post("/orders/preview")
def preview_order(body: PreviewBody, conn: Conn) -> dict[str, object]:
    try:
        return svc.preview(conn, body.idea_id)
    except svc.OrderBlockedError as exc:
        raise _blocked(exc) from None


@router.post("/orders")
def place_order(body: PlaceBody, conn: Conn) -> dict[str, object]:
    try:
        return svc.place(conn, body.idea_id, body.quantity, body.token)
    except svc.OrderBlockedError as exc:
        raise _blocked(exc) from None


@router.post("/controls/kill-switch")
def kill_switch(body: KillSwitchBody, conn: Conn) -> dict[str, object]:
    # Attivare è sempre possibile; disattivare solo se gli ordini sono abilitati.
    if not body.active and get_settings().orders_mode == "disabled":
        raise HTTPException(status_code=409, detail="Ordini disattivati (ORDERS_MODE=disabled)")
    svc.set_kill_switch(conn, body.active)
    conn.commit()
    return {"kill_switch": svc.kill_switch_active(conn)}


@router.post("/ideas/reset")
def reset_ideas(conn: Conn) -> dict[str, object]:
    """Azzera le proposte attive: le nuove arrivano al prossimo aggiornamento dei dati."""
    count = reset_proposals(conn)
    conn.commit()
    return {"annullate": count}
