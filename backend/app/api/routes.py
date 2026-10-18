import time
from datetime import UTC, datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import Connection, and_, func, select

from app.api.deps import get_conn
from app.api.schemas import Candle, Candles, Instrument, Quality, QualityItem
from app.data.models import Timeframe, resample_weekly
from app.data.universe import BY_SYMBOL
from app.db import repository as repo
from app.db.engine import get_engine
from app.db.schema import instruments, prices

router = APIRouter(prefix="/api")

Symbol = Annotated[str, Path(pattern=r"^[A-Z0-9]{2,16}$")]
Conn = Annotated[Connection, Depends(get_conn)]

_quality_cache: tuple[float, Quality] | None = None
QUALITY_TTL = 600


@router.get("/instruments", response_model=list[Instrument])
def list_instruments(conn: Conn) -> list[Instrument]:
    underlying = instruments.alias("u")
    ranked = (
        select(
            prices.c.instrument_id,
            prices.c.close,
            prices.c.ts,
            func.row_number()
            .over(partition_by=prices.c.instrument_id, order_by=prices.c.ts.desc())
            .label("rn"),
        )
        .where(prices.c.timeframe == Timeframe.D1.value)
        .subquery()
    )
    last_two = select(ranked).where(ranked.c.rn <= 2).subquery()
    rows = conn.execute(
        select(instruments, underlying.c.symbol.label("underlying_symbol"))
        .outerjoin(underlying, instruments.c.underlying_id == underlying.c.id)
        .where(instruments.c.active)
        .order_by(instruments.c.id)
    ).mappings()
    closes: dict[int, list[tuple[datetime, float]]] = {}
    for r in conn.execute(select(last_two).order_by(last_two.c.rn)).mappings():
        closes.setdefault(r["instrument_id"], []).append((r["ts"], r["close"]))
    out: list[Instrument] = []
    for r in rows:
        series = closes.get(r["id"], [])
        last = series[0] if series else None
        prev = series[1] if len(series) > 1 else None
        change = (last[1] / prev[1] - 1) * 100 if last and prev else None
        out.append(
            Instrument(
                symbol=r["symbol"],
                name=r["name"],
                kind=r["kind"],
                currency=r["currency"],
                leverage=r["leverage"],
                underlying=r["underlying_symbol"],
                reference_ticker=r["reference_ticker"],
                synthetic=r["underlying_symbol"] is not None,
                last_price=last[1] if last else None,
                change_pct=change,
                last_ts=last[0] if last else None,
            )
        )
    return out


@router.get("/instruments/{symbol}/candles", response_model=Candles)
def candles(
    symbol: Symbol,
    conn: Conn,
    timeframe: Timeframe = Timeframe.D1,
    limit: Annotated[int, Query(ge=10, le=5000)] = 500,
) -> Candles:
    row = conn.execute(
        select(instruments.c.id).where(instruments.c.symbol == symbol)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Strumento non trovato")
    if timeframe is Timeframe.W1:
        daily = repo.load_prices(conn, row, Timeframe.D1, limit=limit * 5 + 5)
        frame = resample_weekly(daily).tail(limit)
        stored_tf = Timeframe.D1
    else:
        frame = repo.load_prices(conn, row, timeframe, limit=limit)
        stored_tf = timeframe
    source = conn.execute(
        select(prices.c.source)
        .where(and_(prices.c.instrument_id == row, prices.c.timeframe == stored_tf.value))
        .order_by(prices.c.ts.desc())
        .limit(1)
    ).scalar_one_or_none()
    naive = pd.DatetimeIndex(frame.index).tz_convert(None).as_unit("s")
    epoch = naive.to_numpy().astype("int64").tolist()
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    return Candles(
        symbol=symbol,
        timeframe=timeframe.value,
        source=source,
        candles=[
            Candle(time=t, open=v[0], high=v[1], low=v[2], close=v[3], volume=v[4])
            for t, v in zip(epoch, values.tolist(), strict=True)
        ],
    )


@router.get("/quality", response_model=Quality)
def data_quality() -> Quality:
    from app.jobs.prices import run_quality

    global _quality_cache
    now = time.monotonic()
    if _quality_cache and now - _quality_cache[0] < QUALITY_TTL:
        return _quality_cache[1]
    reports = run_quality(get_engine())
    items = [QualityItem.model_validate(r.summary()) for r in reports]
    result = Quality(
        generated_at=datetime.now(UTC), complete=all(i.complete for i in items), items=items
    )
    _quality_cache = (now, result)
    return result


__all__ = ["BY_SYMBOL", "router"]
