"""Conto reale come fonte del rischio: posizioni Trading 212 mappate sull'universo."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

import httpx
from sqlalchemy import Connection, select
from sqlalchemy.dialects.postgresql import insert

from app.broker.trading212 import BrokerPosition, BrokerSnapshot, CachedBroker, Trading212ReadOnly
from app.config import get_settings
from app.data.universe import UNIVERSE, InstrumentSpec
from app.db.schema import broker_snapshots
from app.trading.risk import OpenPosition, PortfolioState

# "3USLl_EQ" -> "3USL": il suffisso minuscolo indica la borsa (l = Londra).
_TICKER = re.compile(r"^([A-Z0-9]+)[a-z]*$")


@lru_cache
def get_broker() -> CachedBroker | None:
    s = get_settings()
    if s.t212_api_key is None or s.t212_api_secret is None:
        return None
    client = httpx.Client(headers={"User-Agent": "monstertrade/0.1"})
    return CachedBroker(
        Trading212ReadOnly(
            client,
            s.t212_api_key.get_secret_value(),
            s.t212_api_secret.get_secret_value(),
            s.t212_env,
        )
    )


def match_instrument(ticker: str) -> InstrumentSpec | None:
    base = ticker.split("_", 1)[0]
    m = _TICKER.match(base)
    if not m:
        return None
    code = m.group(1)
    for spec in UNIVERSE:
        if spec.reference_ticker and spec.reference_ticker.upper() == code:
            return spec
    return None


@dataclass(frozen=True)
class MappedPosition:
    position: BrokerPosition
    spec: InstrumentSpec | None

    @property
    def key(self) -> str:
        return self.spec.symbol if self.spec else self.position.ticker

    @property
    def leverage(self) -> float:
        return self.spec.leverage if self.spec else 1.0


def map_positions(snapshot: BrokerSnapshot) -> list[MappedPosition]:
    return [MappedPosition(p, match_instrument(p.ticker)) for p in snapshot.positions]


def day_start_total(conn: Connection, snapshot: BrokerSnapshot) -> float:
    """Valore del conto alla prima lettura della giornata (UTC), salvato una volta al giorno."""
    today = datetime.now(UTC).date()
    conn.execute(
        insert(broker_snapshots)
        .values(
            day=today,
            total=snapshot.summary.total,
            cash=snapshot.summary.cash,
            invested=snapshot.summary.invested,
        )
        .on_conflict_do_nothing(index_elements=[broker_snapshots.c.day])
    )
    value = conn.execute(
        select(broker_snapshots.c.total).where(broker_snapshots.c.day == today)
    ).scalar_one()
    return float(value)


def real_state(conn: Connection, snapshot: BrokerSnapshot) -> PortfolioState:
    mapped = map_positions(snapshot)
    return PortfolioState(
        equity=snapshot.summary.total,
        day_start_equity=day_start_total(conn, snapshot),
        open_positions=[OpenPosition(m.key, m.leverage, m.position.value) for m in mapped],
    )
