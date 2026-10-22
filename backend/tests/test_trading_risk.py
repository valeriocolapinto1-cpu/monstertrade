import pytest

from app.trading.risk import (
    OpenPosition,
    PortfolioState,
    Rejection,
    RiskConfig,
    TradePlan,
    TradeRequest,
    daily_limit_reached,
    plan_trade,
    position_size,
)

CFG = RiskConfig(capital=1000.0)


def state(
    equity: float = 1000.0, start: float | None = None, positions: list[OpenPosition] | None = None
) -> PortfolioState:
    return PortfolioState(equity, start if start is not None else equity, positions or [])


def req(**kw: object) -> TradeRequest:
    base: dict[str, object] = {
        "symbol": "NDX2L",
        "horizon": "swing",
        "leverage": 2.0,
        "entry": 100.0,
        "atr_pct": 2.5,
        "round_trip_cost": 0.002,
    }
    base.update(kw)
    return TradeRequest(**base)  # type: ignore[arg-type]


def test_position_size_formula_from_plan() -> None:
    # Esempio del piano: 1.000 € di capitale, stop al 5%: posizione di 200 €.
    assert position_size(1000, 0.01, 0.05, 0.0) == pytest.approx(200.0)
    # Con i costi la posizione si riduce perché la perdita totale resta 10 €.
    assert position_size(1000, 0.01, 0.05, 0.005) == pytest.approx(10 / 0.055)
    with pytest.raises(ValueError):
        position_size(1000, 0.01, 0.0, 0.0)


def test_plan_stop_target_and_risk_capped_at_one_percent() -> None:
    plan = plan_trade(req(), state(), CFG)
    assert isinstance(plan, TradePlan)
    assert plan.stop_pct == pytest.approx(0.05)  # 2 x ATR 2,5%
    assert plan.stop == pytest.approx(95.0)
    assert plan.target == pytest.approx(110.0)
    assert plan.risk_eur == pytest.approx(10.0, abs=0.01)
    assert plan.costs_eur == pytest.approx(plan.size_eur * 0.002, abs=0.01)


def test_not_convenient_after_costs() -> None:
    # Day trading con ATR piccolo: stop 0,45% e costi 0,5% andata e ritorno.
    out = plan_trade(req(horizon="day", atr_pct=0.3, round_trip_cost=0.005), state(), CFG)
    assert isinstance(out, Rejection) and out.reason.startswith("Non conveniente dopo i costi")


def test_daily_loss_limit_blocks_everything() -> None:
    s = state(equity=969.0, start=1000.0)
    assert daily_limit_reached(s, CFG)
    out = plan_trade(req(), s, CFG)
    assert isinstance(out, Rejection) and "giornaliera" in out.reason
    assert not daily_limit_reached(state(equity=971.0, start=1000.0), CFG)


def test_max_open_positions() -> None:
    positions = [OpenPosition(s, 1, 100) for s in ("SPX", "BTC", "ETH")]
    out = plan_trade(req(), state(positions=positions), CFG)
    assert isinstance(out, Rejection) and "3 posizioni" in out.reason


def test_correlated_with_open_position_rejected() -> None:
    out = plan_trade(
        req(correlations={"NDX3L": 0.99}), state(positions=[OpenPosition("NDX3L", 3, 100)]), CFG
    )
    assert isinstance(out, Rejection) and "correlato con NDX3L" in out.reason
    ok = plan_trade(
        req(correlations={"BTC": 0.3}), state(positions=[OpenPosition("BTC", 1, 100)]), CFG
    )
    assert isinstance(ok, TradePlan) and ok.max_correlation == pytest.approx(0.3)


def test_lev3_exposure_capped_at_thirty_percent() -> None:
    # Già 250 € in 3x: per un nuovo 3x restano 50 € (30% di 1.000).
    positions = [OpenPosition("SPX3L", 3, 250)]
    plan = plan_trade(req(symbol="SOX3L", leverage=3, atr_pct=2.0), state(positions=positions), CFG)
    assert isinstance(plan, TradePlan)
    assert plan.size_eur == pytest.approx(50.0)
    assert plan.risk_eur < 10.0
    full = [OpenPosition("SPX3L", 3, 295)]
    out = plan_trade(req(symbol="SOX3L", leverage=3, atr_pct=2.0), state(positions=full), CFG)
    assert isinstance(out, Rejection) and "minimo acquistabile" in out.reason


def test_short_etf_counts_as_three_x() -> None:
    positions = [OpenPosition("SPX3S", -3, 300)]
    out = plan_trade(req(symbol="NDX3S", leverage=-3), state(positions=positions), CFG)
    assert isinstance(out, Rejection)


def test_size_limited_by_cash() -> None:
    positions = [OpenPosition("SPX", 1, 950)]
    plan = plan_trade(req(symbol="BTC", leverage=1, atr_pct=0.5), state(positions=positions), CFG)
    assert isinstance(plan, TradePlan) and plan.size_eur == pytest.approx(50.0)


def test_duplicate_instrument_rejected() -> None:
    out = plan_trade(req(), state(positions=[OpenPosition("NDX2L", 2, 100)]), CFG)
    assert isinstance(out, Rejection) and "già aperta" in out.reason


def test_minimum_stop_distance() -> None:
    plan = plan_trade(req(atr_pct=0.05, round_trip_cost=0.0), state(), CFG)
    assert isinstance(plan, TradePlan) and plan.stop_pct == pytest.approx(0.005)


def test_small_capital_50_eur() -> None:
    from app.config import Settings

    assert Settings(_env_file=None, capital_eur=50).capital_eur == 50  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        Settings(_env_file=None, capital_eur=49)  # type: ignore[call-arg]
    cfg = RiskConfig(capital=50, min_order=1.0)
    state = PortfolioState(equity=50, day_start_equity=50)
    req = TradeRequest("NDX2L", "swing", 2, 100.0, 2.0, 0.004)
    plan = plan_trade(req, state, cfg)
    assert isinstance(plan, TradePlan)
    assert plan.risk_eur <= 0.5 + 1e-6  # 1% di 50 euro, costi inclusi
    assert 1.0 <= plan.size_eur <= 50
