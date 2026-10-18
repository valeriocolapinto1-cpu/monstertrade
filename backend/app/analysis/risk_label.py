"""Etichetta di rischio di una proposta: Basso, Medio, Alto, Molto alto.

Regole del piano:
- Basso: strumento senza leva, volatilità sotto la mediana, stop breve.
- Medio: leva 2x o crypto maggiori, volatilità nella media.
- Alto: leva 3x, ETF short o settore ristretto, volatilità sopra la mediana.
- Molto alto: day trading con leva 3x, crypto minori, notizie importanti a breve.
Una forte correlazione con le posizioni aperte alza il livello di uno.
"""

from dataclasses import dataclass

from app.data.universe import InstrumentSpec, Kind

LABELS = ("Basso", "Medio", "Alto", "Molto alto")
NARROW_SECTORS = {"SOX"}
MINOR_CRYPTO = {"SOL"}
MAJOR_CRYPTO = {"BTC", "ETH"}
SHORT_STOP_PCT = 5.0


@dataclass(frozen=True)
class RiskInputs:
    horizon: str
    atr_pct: float
    atr_pct_median: float
    stop_distance_pct: float | None = None
    max_correlation_open: float = 0.0
    event_soon: bool = False


def base_symbol(spec: InstrumentSpec) -> str:
    return spec.underlying or spec.symbol


def risk_level(spec: InstrumentSpec, inputs: RiskInputs) -> int:
    lev = spec.leverage
    base = base_symbol(spec)
    crypto = spec.kind in (Kind.CRYPTO, Kind.CRYPTO_ETP)
    if crypto and base in MINOR_CRYPTO:
        level = 3
    elif abs(lev) >= 3 or lev < 0 or base in NARROW_SECTORS:
        level = 2
    elif abs(lev) >= 2 or (crypto and base in MAJOR_CRYPTO):
        level = 1
    else:
        level = 0

    above_median = inputs.atr_pct > inputs.atr_pct_median
    if level == 0 and (above_median or (inputs.stop_distance_pct or 0) > SHORT_STOP_PCT):
        level = 1
    elif level in (1, 2) and inputs.atr_pct > 1.25 * inputs.atr_pct_median:
        level += 1
    if inputs.horizon == "day" and abs(lev) >= 3:
        level = 3
    if inputs.event_soon:
        level = 3
    if inputs.max_correlation_open > 0.8:
        level += 1
    return min(level, 3)


def risk_label(spec: InstrumentSpec, inputs: RiskInputs) -> str:
    return LABELS[risk_level(spec, inputs)]
