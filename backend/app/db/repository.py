from collections.abc import Iterable
from datetime import datetime

import pandas as pd
from sqlalchemy import Connection, and_, func, select
from sqlalchemy.dialects.postgresql import insert

from app.data.models import OHLCV_COLUMNS, Timeframe, empty_ohlcv
from app.data.universe import InstrumentSpec
from app.db.schema import indicators, instruments, prices, sentiment, signals

BATCH = 5000


def sync_instruments(conn: Connection, specs: Iterable[InstrumentSpec]) -> dict[str, int]:
    """Inserisce o aggiorna l'universo; restituisce simbolo -> id."""
    specs = list(specs)
    ids: dict[str, int] = {}
    # Prima i sottostanti, poi gli strumenti che li referenziano.
    for spec in sorted(specs, key=lambda s: s.synthetic):
        values = {
            "symbol": spec.symbol,
            "name": spec.name,
            "kind": spec.kind.value,
            "currency": spec.currency,
            "calendar": spec.calendar.value,
            "leverage": spec.leverage,
            "underlying_id": ids.get(spec.underlying) if spec.underlying else None,
            "ter": spec.ter,
            "reference_ticker": spec.reference_ticker,
            "updated_at": func.now(),
        }
        base = insert(instruments).values(**values)
        upsert = base.on_conflict_do_update(
            index_elements=[instruments.c.symbol],
            set_={k: base.excluded[k] for k in values if k != "symbol"},
        ).returning(instruments.c.id)
        ids[spec.symbol] = int(conn.execute(upsert).scalar_one())
    return ids


def instrument_ids(conn: Connection) -> dict[str, int]:
    rows = conn.execute(select(instruments.c.symbol, instruments.c.id))
    return {symbol: int(id_) for symbol, id_ in rows}


def upsert_prices(
    conn: Connection, instrument_id: int, timeframe: Timeframe, frame: pd.DataFrame, source: str
) -> int:
    if frame.empty:
        return 0
    values = frame[["open", "high", "low", "close"]].to_numpy(dtype="float64")
    volume = frame["volume"].fillna(0.0).to_numpy(dtype="float64")
    rows = [
        {
            "instrument_id": instrument_id,
            "timeframe": timeframe.value,
            "ts": ts.to_pydatetime(),
            "open": float(v[0]),
            "high": float(v[1]),
            "low": float(v[2]),
            "close": float(v[3]),
            "volume": float(vol),
            "source": source,
        }
        for ts, v, vol in zip(frame.index, values, volume, strict=True)
    ]
    stmt = insert(prices)
    stmt = stmt.on_conflict_do_update(
        index_elements=[prices.c.instrument_id, prices.c.timeframe, prices.c.ts],
        set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "volume", "source")},
    )
    for start in range(0, len(rows), BATCH):
        conn.execute(stmt, rows[start : start + BATCH])
    return len(rows)


def load_prices(
    conn: Connection,
    instrument_id: int,
    timeframe: Timeframe,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    conds = [prices.c.instrument_id == instrument_id, prices.c.timeframe == timeframe.value]
    if start is not None:
        conds.append(prices.c.ts >= start)
    if end is not None:
        conds.append(prices.c.ts < end)
    query = select(prices.c.ts, *(prices.c[c] for c in OHLCV_COLUMNS)).where(and_(*conds))
    if limit is not None:
        query = query.order_by(prices.c.ts.desc()).limit(limit)
    else:
        query = query.order_by(prices.c.ts)
    rows = conn.execute(query).all()
    if not rows:
        return empty_ohlcv()
    frame = pd.DataFrame(rows, columns=["ts", *OHLCV_COLUMNS]).set_index("ts")
    frame.index = pd.DatetimeIndex(frame.index).tz_convert("UTC")
    return frame.sort_index().astype("float64")


def last_timestamp(conn: Connection, instrument_id: int, timeframe: Timeframe) -> datetime | None:
    value = conn.execute(
        select(func.max(prices.c.ts)).where(
            prices.c.instrument_id == instrument_id, prices.c.timeframe == timeframe.value
        )
    ).scalar_one_or_none()
    return value


def delete_before(
    conn: Connection, instrument_id: int, timeframe: Timeframe, cutoff: datetime
) -> int:
    result = conn.execute(
        prices.delete().where(
            prices.c.instrument_id == instrument_id,
            prices.c.timeframe == timeframe.value,
            prices.c.ts < cutoff,
        )
    )
    return int(result.rowcount or 0)


def replace_indicators(
    conn: Connection, instrument_id: int, timeframe: Timeframe, wide: pd.DataFrame
) -> int:
    """Sostituisce gli indicatori salvati con la tabella larga (una colonna per nome)."""
    conn.execute(
        indicators.delete().where(
            indicators.c.instrument_id == instrument_id,
            indicators.c.timeframe == timeframe.value,
        )
    )
    rows: list[dict[str, object]] = []
    for name in wide.columns:
        col = wide[name].dropna()
        rows.extend(
            {
                "instrument_id": instrument_id,
                "timeframe": timeframe.value,
                "ts": ts.to_pydatetime(),
                "name": str(name),
                "value": float(v),
            }
            for ts, v in zip(col.index, col.to_numpy(dtype="float64"), strict=True)
        )
    if not rows:
        return 0
    for start in range(0, len(rows), BATCH):
        conn.execute(indicators.insert(), rows[start : start + BATCH])
    return len(rows)


def load_indicators(
    conn: Connection, instrument_id: int, timeframe: Timeframe, names: list[str] | None = None
) -> pd.DataFrame:
    conds = [indicators.c.instrument_id == instrument_id, indicators.c.timeframe == timeframe.value]
    if names:
        conds.append(indicators.c.name.in_(names))
    rows = conn.execute(
        select(indicators.c.ts, indicators.c.name, indicators.c.value).where(and_(*conds))
    ).all()
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows, columns=["ts", "name", "value"])
    wide = frame.pivot(index="ts", columns="name", values="value").sort_index()
    wide.index = pd.DatetimeIndex(wide.index).tz_convert("UTC")
    return wide


def upsert_sentiment(conn: Connection, rows: list[dict[str, object]]) -> int:
    if not rows:
        return 0
    stmt = insert(sentiment)
    stmt = stmt.on_conflict_do_update(
        index_elements=[sentiment.c.instrument_id, sentiment.c.date, sentiment.c.source],
        set_={"score": stmt.excluded.score, "mentions": stmt.excluded.mentions},
    )
    conn.execute(stmt, rows)
    return len(rows)


def load_sentiment(
    conn: Connection, instrument_id: int, sources: list[str] | None = None
) -> pd.DataFrame:
    """Sentiment giornaliero per fonte: colonne date, source, score, mentions."""
    conds = [sentiment.c.instrument_id == instrument_id]
    if sources:
        conds.append(sentiment.c.source.in_(sources))
    rows = conn.execute(
        select(sentiment.c.date, sentiment.c.source, sentiment.c.score, sentiment.c.mentions)
        .where(and_(*conds))
        .order_by(sentiment.c.date)
    ).all()
    return pd.DataFrame(rows, columns=["date", "source", "score", "mentions"])


def daily_sentiment_index(frame: pd.DataFrame) -> pd.Series:
    """Media giornaliera tra le fonti, pesata per numero di menzioni (minimo 1)."""
    if frame.empty:
        return pd.Series(dtype="float64")
    weights = frame["mentions"].clip(lower=1)
    num = (frame["score"] * weights).groupby(frame["date"]).sum()
    den = weights.groupby(frame["date"]).sum()
    out = num / den
    out.index = pd.DatetimeIndex(out.index)
    return out


def replace_signals(
    conn: Connection, instrument_id: int, horizon: str, rows: list[dict[str, object]], keep: int
) -> int:
    if rows:
        stmt = insert(signals)
        stmt = stmt.on_conflict_do_update(
            index_elements=[signals.c.instrument_id, signals.c.horizon, signals.c.ts],
            set_={
                c: stmt.excluded[c]
                for c in ("score", "components", "favorable", "contrary", "risk_label")
            },
        )
        conn.execute(
            stmt, [{"instrument_id": instrument_id, "horizon": horizon, **r} for r in rows]
        )
    # Si tengono solo le ultime `keep` righe per orizzonte.
    cutoff = conn.execute(
        select(signals.c.ts)
        .where(signals.c.instrument_id == instrument_id, signals.c.horizon == horizon)
        .order_by(signals.c.ts.desc())
        .offset(keep)
        .limit(1)
    ).scalar_one_or_none()
    if cutoff is not None:
        conn.execute(
            signals.delete().where(
                signals.c.instrument_id == instrument_id,
                signals.c.horizon == horizon,
                signals.c.ts <= cutoff,
            )
        )
    return len(rows)


def latest_signals(conn: Connection, instrument_id: int | None = None) -> list[dict[str, object]]:
    """Ultimo segnale per strumento e orizzonte."""
    ranked = select(
        signals,
        func.row_number()
        .over(
            partition_by=(signals.c.instrument_id, signals.c.horizon),
            order_by=signals.c.ts.desc(),
        )
        .label("rn"),
    )
    if instrument_id is not None:
        ranked = ranked.where(signals.c.instrument_id == instrument_id)
    sub = ranked.subquery()
    rows = conn.execute(
        select(sub, instruments.c.symbol)
        .join(instruments, instruments.c.id == sub.c.instrument_id)
        .where(sub.c.rn == 1)
    ).mappings()
    return [dict(r) for r in rows]
