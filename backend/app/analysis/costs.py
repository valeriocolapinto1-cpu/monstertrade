"""Modello dei costi per lato (acquisto o vendita), in frazione del controvalore.

Trading 212 non applica commissioni di negoziazione, ma il conto è in euro:
- cambio valuta 0,15% per lato sugli strumenti non in euro;
- spread denaro-lettera stimato per tipo di strumento (metà spread per lato).
Valori prudenti da affinare con i prezzi reali osservati sul broker.
"""

from dataclasses import dataclass

from app.data.universe import InstrumentSpec, Kind

FX_FEE = 0.0015
HALF_SPREAD = {
    Kind.INDEX: 0.0003,  # replicato con un ETF liquido senza leva
    Kind.LEVERAGED_ETF: 0.0010,
    Kind.CRYPTO: 0.0025,  # su Trading 212 la crypto si negozia con spread ampi
    Kind.CRYPTO_ETP: 0.0020,
}


@dataclass(frozen=True)
class CostModel:
    per_side: float

    @property
    def round_trip(self) -> float:
        return 2 * self.per_side


def cost_model(spec: InstrumentSpec) -> CostModel:
    fx = 0.0 if spec.currency == "EUR" else FX_FEE
    return CostModel(per_side=HALF_SPREAD[spec.kind] + fx)
