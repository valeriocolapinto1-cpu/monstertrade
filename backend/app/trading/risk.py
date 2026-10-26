"""Gestione del rischio: dimensione della posizione, stop, obiettivo e limiti fissi.

Tutto si calcola dallo stop, non dal guadagno sperato:

    posizione = capitale x rischio per trade / (distanza dello stop + costi andata e ritorno)

così che la perdita allo stop, costi inclusi, sia al massimo l'1% del capitale.
Un trade che non conviene dopo i costi, o che violerebbe un limite, non viene proposto.
"""

from dataclasses import dataclass, field

# Distanza dello stop in multipli di ATR per orizzonte.
ATR_STOP = {"day": 1.5, "swing": 2.0, "long": 2.5}
# Obiettivo in multipli della distanza dello stop.
REWARD_MULTIPLE = 2.0
# Rapporto guadagno/rischio minimo dopo i costi.
MIN_NET_REWARD_RISK = 1.5
# Stop minimo, per non proporre stop dentro il rumore di uno spread.
MIN_STOP_PCT = 0.005


@dataclass(frozen=True)
class RiskConfig:
    capital: float
    risk_per_trade: float = 0.01
    max_daily_loss: float = 0.03
    max_open_positions: int = 3
    max_lev3_exposure: float = 0.30
    max_correlation: float = 0.80
    min_order: float = 10.0


@dataclass(frozen=True)
class OpenPosition:
    symbol: str
    leverage: float
    size_eur: float


@dataclass
class PortfolioState:
    equity: float
    day_start_equity: float
    open_positions: list[OpenPosition] = field(default_factory=list)
    # "simulazione" (diario) oppure "conto" (Trading 212, sola lettura).
    source: str = "simulazione"
    # Liquidità reale del conto; se assente si ricava da capitale meno investito.
    cash: float | None = None

    @property
    def day_pnl(self) -> float:
        return self.equity - self.day_start_equity

    def lev3_exposure(self) -> float:
        return sum(p.size_eur for p in self.open_positions if abs(p.leverage) >= 3)

    def invested(self) -> float:
        return sum(p.size_eur for p in self.open_positions)


@dataclass(frozen=True)
class TradeRequest:
    symbol: str
    horizon: str
    leverage: float
    entry: float
    atr_pct: float  # ATR dello strumento stesso, in % del prezzo
    round_trip_cost: float  # frazione del controvalore (spread e cambio, andata e ritorno)
    correlations: dict[str, float] = field(default_factory=dict)  # con le posizioni aperte


@dataclass(frozen=True)
class TradePlan:
    entry: float
    stop: float
    target: float
    stop_pct: float
    target_pct: float
    size_eur: float
    risk_eur: float
    costs_eur: float
    net_reward_risk: float
    max_correlation: float
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rejection:
    reason: str


def daily_limit_reached(state: PortfolioState, cfg: RiskConfig) -> bool:
    return state.day_pnl <= -cfg.max_daily_loss * state.day_start_equity


def position_size(
    capital: float, risk_per_trade: float, stop_pct: float, round_trip: float
) -> float:
    """Controvalore in euro tale che la perdita allo stop, costi inclusi, sia il rischio massimo."""
    if stop_pct <= 0:
        raise ValueError("la distanza dello stop deve essere positiva")
    return capital * risk_per_trade / (stop_pct + round_trip)


def plan_trade(req: TradeRequest, state: PortfolioState, cfg: RiskConfig) -> TradePlan | Rejection:
    if daily_limit_reached(state, cfg):
        return Rejection(
            "Perdita giornaliera massima (3%) raggiunta: nessuna proposta fino a domani"
        )
    if len(state.open_positions) >= cfg.max_open_positions:
        return Rejection(f"Già {cfg.max_open_positions} posizioni aperte o proposte")
    if any(p.symbol == req.symbol for p in state.open_positions):
        return Rejection("Posizione già aperta su questo strumento")
    worst = max(req.correlations.items(), key=lambda kv: abs(kv[1]), default=(None, 0.0))
    if worst[0] is not None and worst[1] > cfg.max_correlation:
        return Rejection(f"Troppo correlato con {worst[0]} ({worst[1]:.2f})")
    if req.entry <= 0 or req.atr_pct <= 0:
        return Rejection("Dati insufficienti per calcolare lo stop")

    stop_pct = max(ATR_STOP[req.horizon] * req.atr_pct / 100, MIN_STOP_PCT)
    target_pct = REWARD_MULTIPLE * stop_pct
    rt = req.round_trip_cost
    net_rr = (target_pct - rt) / (stop_pct + rt)
    if net_rr < MIN_NET_REWARD_RISK:
        return Rejection(
            f"Non conveniente dopo i costi: guadagno/rischio netto {net_rr:.2f} "
            f"(minimo {MIN_NET_REWARD_RISK:.1f})"
        )

    notes: list[str] = []
    size = position_size(state.equity, cfg.risk_per_trade, stop_pct, rt)
    cash = state.cash if state.cash is not None else max(state.equity - state.invested(), 0.0)
    if size > cash:
        size = cash
        notes.append("Dimensione ridotta alla liquidità disponibile")
    if abs(req.leverage) >= 3:
        room = cfg.max_lev3_exposure * state.equity - state.lev3_exposure()
        if size > room:
            size = max(room, 0.0)
            notes.append("Dimensione ridotta per il limite del 30% in leva 3x")
    if size < cfg.min_order:
        return Rejection(f"Sotto il minimo acquistabile ({size:.2f} € con i limiti di rischio)")

    return TradePlan(
        entry=req.entry,
        stop=req.entry * (1 - stop_pct),
        target=req.entry * (1 + target_pct),
        stop_pct=stop_pct,
        target_pct=target_pct,
        size_eur=round(size, 2),
        risk_eur=round(size * (stop_pct + rt), 2),
        costs_eur=round(size * rt, 2),
        net_reward_risk=round(net_rr, 2),
        max_correlation=float(worst[1]),
        notes=tuple(notes),
    )
