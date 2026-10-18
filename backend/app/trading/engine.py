"""Motore delle proposte e simulazione: collega segnali, rischio e diario.

Il job (`app.jobs.trading`) chiama `run`; l'API usa `evaluate` in sola lettura per
mostrare anche perché un candidato non è stato proposto.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pandas as pd
from sqlalchemy import Connection, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.analysis import indicators as ind
from app.analysis.costs import cost_model
from app.analysis.signals import ENTER_SCORE, EXIT_SCORE, HORIZON_TIMEFRAME
from app.config import Settings
from app.data.models import Timeframe
from app.data.universe import BY_SYMBOL, Calendar, InstrumentSpec
from app.db import repository as repo
from app.db.schema import instruments, trade_ideas, trades
from app.trading.risk import (
    OpenPosition,
    PortfolioState,
    Rejection,
    RiskConfig,
    TradePlan,
    TradeRequest,
    plan_trade,
)
from app.trading.simulator import MAX_BARS, Entry, Exit, find_entry, find_exit, pnl

EXPIRY = {"day": timedelta(hours=2), "swing": timedelta(days=4), "long": timedelta(days=10)}
ACTIVE = ("proposta", "aperta")
CORRELATION_WINDOW = 90


def risk_config(settings: Settings) -> RiskConfig:
    return RiskConfig(
        capital=settings.capital_eur,
        risk_per_trade=settings.risk_per_trade,
        max_daily_loss=settings.max_daily_loss,
        max_open_positions=settings.max_open_positions,
        max_lev3_exposure=settings.max_lev3_exposure,
        max_correlation=settings.max_correlation,
        min_order=settings.min_order_eur,
    )


def bars_for(conn: Connection, symbol: str, horizon: str, limit: int | None = None) -> pd.DataFrame:
    from app.analysis.scoring import load_frame

    return load_frame(conn, symbol, HORIZON_TIMEFRAME[horizon], limit)


# --- Stato del portafoglio -------------------------------------------------------


@dataclass
class Position:
    trade_id: int
    idea_id: int
    symbol: str
    horizon: str
    leverage: float
    entry_ts: datetime
    entry_price: float
    size_eur: float
    stop: float
    target: float
    last_price: float
    day_start_price: float

    @property
    def value(self) -> float:
        return self.size_eur * self.last_price / self.entry_price

    @property
    def unrealized(self) -> float:
        return self.value - self.size_eur


def open_positions(conn: Connection) -> list[Position]:
    rows = (
        conn.execute(
            select(
                trades,
                trade_ideas.c.horizon,
                trade_ideas.c.stop,
                trade_ideas.c.target,
                instruments.c.symbol,
                instruments.c.leverage,
            )
            .join(trade_ideas, trade_ideas.c.id == trades.c.idea_id)
            .join(instruments, instruments.c.id == trade_ideas.c.instrument_id)
            .where(trades.c.status == "aperta")
        )
        .mappings()
        .all()
    )
    today = pd.Timestamp(datetime.now(UTC).date(), tz="UTC")
    out: list[Position] = []
    for r in rows:
        daily = bars_for(conn, r["symbol"], "swing", limit=10)
        last = float(daily["close"].iloc[-1]) if not daily.empty else r["entry_price"]
        before = daily[daily.index < today]
        start = float(before["close"].iloc[-1]) if not before.empty else r["entry_price"]
        if pd.Timestamp(r["entry_ts"]) >= today:
            start = r["entry_price"]
        out.append(
            Position(
                r["id"],
                r["idea_id"],
                r["symbol"],
                r["horizon"],
                r["leverage"],
                r["entry_ts"],
                r["entry_price"],
                r["size_eur"],
                r["stop"],
                r["target"],
                last,
                start,
            )
        )
    return out


def realized(conn: Connection, since: datetime | None = None) -> float:
    query = select(func.coalesce(func.sum(trades.c.pnl_eur), 0.0)).where(
        trades.c.status == "chiusa"
    )
    if since is not None:
        query = query.where(trades.c.exit_ts >= since)
    return float(conn.execute(query).scalar_one())


def portfolio_state(conn: Connection, cfg: RiskConfig) -> tuple[PortfolioState, list[Position]]:
    positions = open_positions(conn)
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    equity = cfg.capital + realized(conn) + sum(p.unrealized for p in positions)
    day_change = realized(conn, today) + sum(
        p.size_eur * (p.last_price - p.day_start_price) / p.entry_price for p in positions
    )
    state = PortfolioState(
        equity=equity,
        day_start_equity=equity - day_change,
        open_positions=[OpenPosition(p.symbol, p.leverage, p.size_eur) for p in positions],
    )
    return state, positions


# --- Candidati e proposte -------------------------------------------------------


@dataclass
class Candidate:
    spec: InstrumentSpec
    horizon: str
    score: float
    signal_ts: datetime
    signal: dict[str, object]
    outcome: TradePlan | Rejection
    warnings: list[str] = field(default_factory=list)
    motivation: str = ""


def correlations(conn: Connection, symbol: str, others: list[str]) -> dict[str, float]:
    if not others:
        return {}
    ids = repo.instrument_ids(conn)
    closes = {
        s: repo.load_prices(conn, ids[s], Timeframe.D1, limit=CORRELATION_WINDOW * 2)["close"]
        for s in {symbol, *others}
        if s in ids
    }
    table = pd.DataFrame(closes).dropna()
    if symbol not in table:
        return {}
    matrix = ind.correlation_matrix(table, CORRELATION_WINDOW)
    row = matrix[symbol]
    return {o: float(row[o]) for o in others if o in row.index and pd.notna(row[o])}


def motivation(
    horizon: str, score: float, signal: dict[str, object], plan: TradePlan, risk_label: str
) -> str:
    labels = {"day": "day trading", "swing": "swing", "long": "lungo periodo"}
    pro = [str(e["label"]).lower() for e in list(signal["favorable"])[:2]]  # type: ignore[call-overload]
    con = [str(e["label"]).lower() for e in list(signal["contrary"])[:1]]  # type: ignore[call-overload]
    first = f"Score {labels[horizon]} {score:+.0f}: " + (", ".join(pro) or "trend favorevole") + "."

    def pct(x: float) -> str:
        return f"{x * 100:.1f}".replace(".", ",")

    second = (f"Contro: {con[0]}. " if con else "") + (
        f"Rischio {risk_label.lower()}, stop a -{pct(plan.stop_pct)}% "
        f"e obiettivo a +{pct(plan.target_pct)}%."
    )
    return f"{first}\n{second}"


def candidate_warnings(spec: InstrumentSpec, horizon: str, adx: float | None) -> list[str]:
    out: list[str] = []
    if spec.kind.value == "index":
        out.append("Indice: si opera con un ETF senza leva che lo replica")
    if spec.kind.value == "crypto":
        out.append("Su Trading 212 la crypto si compra con ETP (o CFD): preferisci l'ETP")
    if spec.synthetic and spec.kind.value == "leveraged_etf":
        out.append("Prezzi da serie sintetica: verifica la quotazione reale su Trading 212")
        if horizon == "long":
            out.append("ETF a leva su orizzonte lungo: il decadimento pesa, controlla spesso")
        if adx is not None and adx < 20:
            out.append("Mercato laterale (ADX sotto 20): decadimento della leva più forte")
    if horizon == "day":
        out.append("Day trading: costi alti rispetto al movimento atteso")
    return out


def evaluate(conn: Connection, cfg: RiskConfig) -> tuple[list[Candidate], PortfolioState]:
    """Valuta tutti gli score sopra la soglia applicando i limiti, dal più forte al più debole."""
    state, _ = portfolio_state(conn, cfg)
    ids = repo.instrument_ids(conn)
    pending = conn.execute(
        select(instruments.c.symbol, instruments.c.leverage, trade_ideas.c.size_eur)
        .join(trade_ideas, trade_ideas.c.instrument_id == instruments.c.id)
        .where(trade_ideas.c.status == "proposta")
    ).all()
    active = {str(r[0]) for r in pending}
    # Le proposte non ancora aperte contano già nei limiti (la simulazione le aprirà).
    state.open_positions.extend(OpenPosition(str(s), float(lv), float(sz)) for s, lv, sz in pending)
    rows = [r for r in repo.latest_signals(conn) if r["symbol"] in BY_SYMBOL]
    rows.sort(key=lambda r: -float(str(r["score"])))
    out: list[Candidate] = []
    for r in rows:
        score = float(str(r["score"]))
        if score <= ENTER_SCORE:
            continue
        spec = BY_SYMBOL[str(r["symbol"])]
        horizon = str(r["horizon"])
        if spec.symbol not in ids:
            continue
        bars = bars_for(conn, spec.symbol, horizon, limit=300)
        if bars.empty:
            continue
        atr_pct = float((ind.atr(bars) / bars["close"] * 100).iloc[-1])
        adx = float(ind.adx(bars)["adx"].iloc[-1]) if len(bars) > 30 else None
        holding = [p.symbol for p in state.open_positions]
        if spec.symbol in active:
            outcome: TradePlan | Rejection = Rejection("Proposta già attiva su questo strumento")
        else:
            outcome = plan_trade(
                TradeRequest(
                    spec.symbol,
                    horizon,
                    spec.leverage,
                    float(bars["close"].iloc[-1]),
                    atr_pct,
                    cost_model(spec).round_trip,
                    correlations(conn, spec.symbol, holding),
                ),
                state,
                cfg,
            )
        signal_ts = r["ts"]
        if not isinstance(signal_ts, datetime):
            continue
        cand = Candidate(
            spec,
            horizon,
            score,
            signal_ts,
            r,
            outcome,
            candidate_warnings(spec, horizon, adx),
        )
        if isinstance(outcome, TradePlan):
            cand.motivation = motivation(horizon, score, r, outcome, str(r["risk_label"]))
            cand.warnings.extend(outcome.notes)
            # La proposta occupa posto e rischio come se fosse aperta (la simulazione la apre).
            state.open_positions.append(OpenPosition(spec.symbol, spec.leverage, outcome.size_eur))
            active.add(spec.symbol)
        out.append(cand)
    return out, state


def save_proposals(conn: Connection, candidates: list[Candidate], now: datetime) -> list[int]:
    ids = repo.instrument_ids(conn)
    created: list[int] = []
    for c in candidates:
        if not isinstance(c.outcome, TradePlan):
            continue
        plan = c.outcome
        stmt = (
            pg_insert(trade_ideas)
            .values(
                instrument_id=ids[c.spec.symbol],
                horizon=c.horizon,
                signal_ts=c.signal_ts,
                score=c.score,
                entry=plan.entry,
                stop=plan.stop,
                target=plan.target,
                size_eur=plan.size_eur,
                risk_eur=plan.risk_eur,
                costs_eur=plan.costs_eur,
                risk_label=str(c.signal["risk_label"]),
                motivation=c.motivation,
                warnings=c.warnings,
                expires_at=now + EXPIRY[c.horizon],
            )
            # Lo stesso segnale non genera due proposte.
            .on_conflict_do_nothing(constraint="uq_trade_ideas_signal")
            .returning(trade_ideas.c.id)
        )
        new_id = conn.execute(stmt).scalar_one_or_none()
        if new_id is not None:
            created.append(int(new_id))
    return created


# --- Simulazione -----------------------------------------------------------------


def simulate(conn: Connection, now: datetime) -> dict[str, int]:
    counts = {"aperti": 0, "chiusi": 0, "scaduti": 0}
    pending = (
        conn.execute(
            select(trade_ideas, instruments.c.symbol)
            .join(instruments, instruments.c.id == trade_ideas.c.instrument_id)
            .where(trade_ideas.c.status == "proposta")
        )
        .mappings()
        .all()
    )
    for idea in pending:
        bars = bars_for(conn, idea["symbol"], idea["horizon"], limit=400)
        entry = find_entry(bars, idea["signal_ts"])
        if entry is None:
            if now >= idea["expires_at"]:
                conn.execute(
                    update(trade_ideas)
                    .where(trade_ideas.c.id == idea["id"])
                    .values(status="scaduta")
                )
                counts["scaduti"] += 1
            continue
        conn.execute(
            insert(trades).values(
                idea_id=idea["id"],
                entry_ts=entry.ts,
                entry_price=entry.price,
                size_eur=idea["size_eur"],
            )
        )
        conn.execute(
            update(trade_ideas).where(trade_ideas.c.id == idea["id"]).values(status="aperta")
        )
        counts["aperti"] += 1

    latest = {
        (str(r["symbol"]), str(r["horizon"])): float(str(r["score"]))
        for r in repo.latest_signals(conn)
    }
    for pos in open_positions(conn):
        spec = BY_SYMBOL[pos.symbol]
        bars = bars_for(conn, pos.symbol, pos.horizon, limit=600)
        flat = pos.horizon == "day" and spec.calendar is Calendar.NYSE
        exit_ = find_exit(
            bars,
            Entry(pos.entry_ts, pos.entry_price),
            pos.stop,
            pos.target,
            MAX_BARS[pos.horizon],
            flat,
        )
        if exit_ is None and latest.get((pos.symbol, pos.horizon), 100.0) < EXIT_SCORE:
            last = bars.iloc[-1]
            exit_ = Exit(bars.index[-1].to_pydatetime(), float(last["close"]), "segnale")
        if exit_ is None:
            continue
        net, fees = pnl(pos.size_eur, pos.entry_price, exit_.price, cost_model(spec).per_side)
        conn.execute(
            update(trades)
            .where(trades.c.id == pos.trade_id)
            .values(
                exit_ts=exit_.ts,
                exit_price=exit_.price,
                exit_reason=exit_.reason,
                pnl_eur=round(net, 2),
                fees_eur=round(fees, 2),
                status="chiusa",
            )
        )
        conn.execute(
            update(trade_ideas).where(trade_ideas.c.id == pos.idea_id).values(status="chiusa")
        )
        counts["chiusi"] += 1
    return counts
