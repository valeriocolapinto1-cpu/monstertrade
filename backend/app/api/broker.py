"""Conto Trading 212 reale, in sola lettura."""

from fastapi import APIRouter, HTTPException

from app.api import deps
from app.broker.service import get_broker, map_positions, real_state
from app.broker.trading212 import BrokerError
from app.config import get_settings
from app.trading.engine import risk_config
from app.trading.risk import daily_limit_reached

router = APIRouter(prefix="/api/broker")


@router.get("/portfolio")
def broker_portfolio() -> dict[str, object]:
    broker = get_broker()
    if broker is None:
        return {"configured": False}
    try:
        snap = broker.snapshot()
    except BrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    cfg = risk_config(get_settings())
    # Il database serve solo se il broker è configurato (valore di inizio giornata).
    with deps.connection() as conn:
        state = real_state(conn, snap)
        conn.commit()
    mapped = map_positions(snap)
    return {
        "configured": True,
        "env": broker.broker.env,
        "read_only": True,
        "summary": {
            "currency": snap.summary.currency,
            "total": snap.summary.total,
            "cash": snap.summary.cash,
            "invested": snap.summary.invested,
            "unrealized_pnl": snap.summary.unrealized_pnl,
        },
        "risk": {
            "day_pnl": round(state.day_pnl, 2),
            "day_pnl_limit": round(-cfg.max_daily_loss * state.day_start_equity, 2),
            "daily_limit_reached": daily_limit_reached(state, cfg),
            "positions": len(state.open_positions),
            "max_positions": cfg.max_open_positions,
            "lev3_exposure": round(state.lev3_exposure(), 2),
            "lev3_limit": round(cfg.max_lev3_exposure * state.equity, 2),
            "risk_per_trade": round(cfg.risk_per_trade * state.equity, 2),
        },
        "positions": [
            {
                "ticker": m.position.ticker,
                "symbol": m.spec.symbol if m.spec else None,
                "name": m.spec.name if m.spec else None,
                "leverage": m.leverage if m.spec else None,
                "quantity": m.position.quantity,
                "average_price": m.position.average_price,
                "current_price": m.position.current_price,
                "value": m.position.value,
                "pnl": m.position.unrealized_pnl,
            }
            for m in mapped
        ],
    }
