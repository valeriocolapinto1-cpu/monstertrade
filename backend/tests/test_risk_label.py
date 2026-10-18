import pytest

from app.analysis.risk_label import RiskInputs, risk_label
from app.data.universe import BY_SYMBOL


def inputs(
    horizon: str = "swing", atr: float = 1.0, median: float = 1.0, **kw: object
) -> RiskInputs:
    return RiskInputs(horizon=horizon, atr_pct=atr, atr_pct_median=median, **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("symbol", "case", "expected"),
    [
        ("SPX", inputs(atr=0.8), "Basso"),
        ("SPX", inputs(atr=1.2), "Medio"),  # volatilità sopra la mediana
        ("SPX", inputs(atr=0.8, stop_distance_pct=8.0), "Medio"),  # stop non breve
        ("NDX2L", inputs(), "Medio"),
        ("BTC", inputs(), "Medio"),
        ("BTCETP", inputs(), "Medio"),
        ("SPX3L", inputs(), "Alto"),
        ("SPX3S", inputs(), "Alto"),  # ETF short
        ("SOX", inputs(atr=0.8), "Alto"),  # settore ristretto
        ("NDX2L", inputs(atr=1.5), "Alto"),  # volatilità ben sopra la mediana
        ("SPX3L", inputs(atr=1.5), "Molto alto"),
        ("SPX3L", inputs(horizon="day"), "Molto alto"),  # day trading con leva 3x
        ("SOL", inputs(), "Molto alto"),  # crypto minore
        ("SPX", inputs(atr=0.8, event_soon=True), "Molto alto"),
        ("NDX2L", inputs(max_correlation_open=0.9), "Alto"),  # correlato a posizioni aperte
    ],
)
def test_risk_label_rules(symbol: str, case: RiskInputs, expected: str) -> None:
    assert risk_label(BY_SYMBOL[symbol], case) == expected
