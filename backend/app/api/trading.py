"""API di sola lettura per Oggi, Portafoglio e Diario. Nessuna scrittura esposta."""

from datetime import UTC, datetime
from typing import Annotated, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection, Select, select

from app.api.deps import get_conn
from app.config import get_settings
from app.data.universe import BY_SYMBOL
from app.db.schema import instruments, trade_ideas, trades
from app.trading.engine import (
    correlations,
    current_state,
    evaluate,
    portfolio_state,
    risk_config,
)
from app.trading.risk import Rejection, daily_limit_reached

router = APIRouter(prefix="/api")
Conn = Annotated[Connection, Depends(get_conn)]


def _iso(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _idea(row: dict[str, object]) -> dict[str, object]:
    spec = BY_SYMBOL.get(str(row["symbol"]))
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "name": spec.name if spec else row["symbol"],
        "leverage": spec.leverage if spec else 1,
        "horizon": row["horizon"],
        "created_at": _iso(row["created_at"]),
        "score": row["score"],
        "entry": row["entry"],
        "stop": row["stop"],
        "target": row["target"],
        "size_eur": row["size_eur"],
        "risk_eur": row["risk_eur"],
        "costs_eur": row["costs_eur"],
        "risk_label": row["risk_label"],
        "motivation": row["motivation"],
        "warnings": row["warnings"],
        "status": row["status"],
        "expires_at": _iso(row["expires_at"]),
    }


def _ideas_query() -> Select[Any]:
    return select(trade_ideas, instruments.c.symbol).join(
        instruments, instruments.c.id == trade_ideas.c.instrument_id
    )


@router.get("/today")
def today(conn: Conn) -> dict[str, object]:
    cfg = risk_config(get_settings())
    active = (
        conn.execute(
            _ideas_query()
            .where(trade_ideas.c.status == "proposta")
            .order_by(trade_ideas.c.score.desc())
        )
        .mappings()
        .all()
    )
    candidates, _ = evaluate(conn, cfg)
    state = current_state(conn, cfg)
    skipped = [
        {
            "symbol": c.spec.symbol,
            "name": c.spec.name,
            "horizon": c.horizon,
            "score": c.score,
            "reason": c.outcome.reason,
        }
        for c in candidates
        if isinstance(c.outcome, Rejection) and "già attiva" not in c.outcome.reason
    ]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "risk_source": state.source,
        "capital": cfg.capital
        if state.source == "simulazione"
        else round(state.day_start_equity, 2),
        "equity": round(state.equity, 2),
        "day_pnl": round(state.day_pnl, 2),
        "daily_limit_reached": daily_limit_reached(state, cfg),
        "open_positions": len(state.open_positions) + len(active),
        "limits": {
            "risk_per_trade": cfg.risk_per_trade,
            "max_daily_loss": cfg.max_daily_loss,
            "max_open_positions": cfg.max_open_positions,
            "max_lev3_exposure": cfg.max_lev3_exposure,
        },
        "proposals": [_idea(dict(r)) for r in active],
        "skipped": skipped[:12],
    }


@router.get("/portfolio")
def portfolio(conn: Conn) -> dict[str, object]:
    cfg = risk_config(get_settings())
    state, positions = portfolio_state(conn, cfg)
    symbols = [p.symbol for p in positions]
    corr: dict[str, dict[str, float]] = {
        s: correlations(conn, s, [o for o in symbols if o != s]) for s in symbols
    }
    lev3 = state.lev3_exposure()
    return {
        "capital": cfg.capital,
        "equity": round(state.equity, 2),
        "invested": round(state.invested(), 2),
        "cash": round(state.equity - state.invested(), 2),
        "day_pnl": round(state.day_pnl, 2),
        "day_pnl_limit": round(-cfg.max_daily_loss * state.day_start_equity, 2),
        "lev3_exposure": round(lev3, 2),
        "lev3_limit": round(cfg.max_lev3_exposure * state.equity, 2),
        "positions": [
            {
                "symbol": p.symbol,
                "name": BY_SYMBOL[p.symbol].name,
                "leverage": p.leverage,
                "horizon": p.horizon,
                "entry_ts": _iso(p.entry_ts),
                "entry_price": p.entry_price,
                "last_price": p.last_price,
                "stop": p.stop,
                "target": p.target,
                "size_eur": p.size_eur,
                "value": round(p.value, 2),
                "pnl": round(p.unrealized, 2),
                "pnl_pct": round((p.last_price / p.entry_price - 1) * 100, 2),
            }
            for p in positions
        ],
        "correlations": corr,
    }


def journal_stats(closed: pd.DataFrame, capital: float) -> dict[str, float | int | None]:
    if closed.empty:
        return {
            "trades": 0,
            "win_rate": None,
            "avg_pnl": None,
            "avg_pnl_pct": None,
            "total_pnl": 0.0,
            "max_drawdown": None,
            "fees": 0.0,
        }
    pnl = closed["pnl_eur"].astype(float)
    equity = capital + pnl.cumsum()
    peak = np.maximum.accumulate(np.r_[capital, equity.to_numpy()])[1:]
    drawdown = float((equity.to_numpy() / peak - 1).min())
    pct = (closed["exit_price"] / closed["entry_price"] - 1) * 100
    return {
        "trades": len(closed),
        "win_rate": float((pnl > 0).mean()),
        "avg_pnl": float(pnl.mean()),
        "avg_pnl_pct": float(pct.mean()),
        "total_pnl": float(pnl.sum()),
        "max_drawdown": min(drawdown, 0.0),
        "fees": float(closed["fees_eur"].astype(float).sum()),
    }


@router.get("/journal")
def journal(conn: Conn, limit: Annotated[int, Query(ge=1, le=500)] = 200) -> dict[str, object]:
    cfg = risk_config(get_settings())
    rows = (
        conn.execute(
            select(
                trade_ideas,
                instruments.c.symbol,
                trades.c.entry_ts,
                trades.c.entry_price,
                trades.c.exit_ts,
                trades.c.exit_price,
                trades.c.exit_reason,
                trades.c.pnl_eur,
                trades.c.fees_eur,
                trades.c.mode,
            )
            .join(instruments, instruments.c.id == trade_ideas.c.instrument_id)
            .outerjoin(trades, trades.c.idea_id == trade_ideas.c.id)
            .order_by(trade_ideas.c.created_at.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    items = []
    for r in rows:
        item = _idea(dict(r))
        item.update(
            {
                "entry_ts": _iso(r["entry_ts"]),
                "entry_price": r["entry_price"],
                "exit_ts": _iso(r["exit_ts"]),
                "exit_price": r["exit_price"],
                "exit_reason": r["exit_reason"],
                "pnl_eur": r["pnl_eur"],
                "fees_eur": r["fees_eur"],
                "mode": r["mode"],
            }
        )
        items.append(item)
    closed = (
        pd.DataFrame([i for i in items if i["exit_ts"] is not None]).sort_values("exit_ts")
        if any(i["exit_ts"] for i in items)
        else pd.DataFrame()
    )
    return {"stats": journal_stats(closed, cfg.capital), "items": items}
