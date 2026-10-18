import json
import math
import time
from datetime import UTC, datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import Connection, and_, func, select

from app.analysis import indicators as ind
from app.analysis.compute import compute_all, summary_metrics
from app.analysis.signals import WEIGHTS
from app.api.deps import get_conn
from app.api.schemas import (
    Candle,
    Candles,
    Correlations,
    Indicators,
    Instrument,
    LevelOut,
    Quality,
    QualityItem,
)
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


def _instrument_id(conn: Connection, symbol: str) -> int:
    row = conn.execute(
        select(instruments.c.id).where(instruments.c.symbol == symbol)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Strumento non trovato")
    return int(row)


def _clean(values: pd.Series) -> list[float | None]:
    return [None if v is None or not math.isfinite(v) else round(float(v), 6) for v in values]


def _finite(value: float) -> float | None:
    return value if value is not None and math.isfinite(value) else None


WARMUP = 300


@router.get("/instruments/{symbol}/indicators", response_model=Indicators)
def instrument_indicators(
    symbol: Symbol,
    conn: Conn,
    timeframe: Timeframe = Timeframe.D1,
    limit: Annotated[int, Query(ge=10, le=5000)] = 500,
) -> Indicators:
    spec = BY_SYMBOL.get(symbol)
    if spec is None:
        raise HTTPException(status_code=404, detail="Strumento non trovato")
    iid = _instrument_id(conn, symbol)

    def load(instrument_id: int) -> pd.DataFrame:
        if timeframe is Timeframe.W1:
            daily = repo.load_prices(conn, instrument_id, Timeframe.D1)
            return resample_weekly(daily).tail(limit + WARMUP)
        return repo.load_prices(conn, instrument_id, timeframe, limit=limit + WARMUP)

    prices = load(iid)
    if prices.empty:
        raise HTTPException(status_code=404, detail="Nessun prezzo per questo intervallo")
    under = None
    if spec.underlying:
        under = load(_instrument_id(conn, spec.underlying))["close"]
    wide = compute_all(prices, timeframe, spec.calendar, spec.leverage, under)
    full_metrics = summary_metrics(prices.tail(limit), timeframe, spec.calendar)
    wide = wide.tail(limit)
    naive = pd.DatetimeIndex(wide.index).tz_convert(None).as_unit("s")
    last = wide.iloc[-1]
    return Indicators(
        symbol=symbol,
        timeframe=timeframe.value,
        time=naive.to_numpy().astype("int64").tolist(),
        series={str(c): _clean(wide[c]) for c in wide.columns},
        levels=[
            LevelOut(price=lv.price, touches=lv.touches, kind=lv.kind)
            for lv in ind.support_resistance(prices)
        ],
        fibonacci=ind.fibonacci(prices),
        metrics={k: _finite(v) for k, v in full_metrics.items()},
        latest={str(k): _finite(float(v)) for k, v in last.items()},
    )


@router.get("/correlations", response_model=Correlations)
def correlations(conn: Conn, window: Annotated[int, Query(ge=30, le=500)] = 90) -> Correlations:
    closes: dict[str, pd.Series] = {}
    ids = repo.instrument_ids(conn)
    for spec in BY_SYMBOL.values():
        if spec.symbol in ids:
            frame = repo.load_prices(conn, ids[spec.symbol], Timeframe.D1, limit=window * 2)
            if not frame.empty:
                closes[spec.symbol] = frame["close"]
    # Le crypto quotano anche nel fine settimana: si confrontano solo i giorni comuni.
    table = pd.DataFrame(closes).dropna()
    matrix = ind.correlation_matrix(table, window)
    symbols = list(matrix.columns)
    return Correlations(
        window=window,
        symbols=symbols,
        matrix=[_clean(matrix[s].reindex(symbols)) for s in symbols],
    )


_backtest_cache: tuple[float, dict[str, object]] | None = None
BACKTEST_TTL = 6 * 3600


@router.get("/backtest")
def backtest_report(
    symbol: Annotated[str | None, Query(pattern=r"^[A-Z0-9]{2,16}$")] = None,
) -> dict[str, object]:
    """Rapporto del backtest: dal file del job se recente, altrimenti ricalcolato."""
    from app.jobs.backtest import report_path, run_report

    global _backtest_cache
    now = time.monotonic()
    if _backtest_cache is None or now - _backtest_cache[0] > BACKTEST_TTL:
        path = report_path()
        if path.exists() and time.time() - path.stat().st_mtime < BACKTEST_TTL:
            report = json.loads(path.read_text())
        else:
            report = run_report(get_engine())
        _backtest_cache = (now, report)
    report = dict(_backtest_cache[1])
    if symbol is not None:
        rows = report.get("results", [])
        report["results"] = [r for r in rows if isinstance(r, dict) and r["symbol"] == symbol]
    return report


def _signal_out(row: dict[str, object]) -> dict[str, object]:
    ts = row["ts"]
    return {
        "symbol": row["symbol"],
        "horizon": row["horizon"],
        "ts": ts.isoformat() if isinstance(ts, datetime) else ts,
        "score": row["score"],
        "components": row["components"],
        "favorable": row["favorable"],
        "contrary": row["contrary"],
        "risk_label": row["risk_label"],
        "weights": WEIGHTS[str(row["horizon"])],
    }


@router.get("/signals")
def all_signals(conn: Conn) -> list[dict[str, object]]:
    """Ultimo score per strumento e orizzonte."""
    return [_signal_out(r) for r in repo.latest_signals(conn)]


@router.get("/instruments/{symbol}/signals")
def instrument_signals(symbol: Symbol, conn: Conn) -> list[dict[str, object]]:
    return [_signal_out(r) for r in repo.latest_signals(conn, _instrument_id(conn, symbol))]


@router.get("/instruments/{symbol}/sentiment")
def instrument_sentiment(
    symbol: Symbol, conn: Conn, days: Annotated[int, Query(ge=1, le=365)] = 30
) -> dict[str, object]:
    """Sentiment del sottostante negli ultimi giorni, per fonte."""
    spec = BY_SYMBOL.get(symbol)
    if spec is None:
        raise HTTPException(status_code=404, detail="Strumento non trovato")
    base = spec.underlying or symbol
    frame = repo.load_sentiment(conn, _instrument_id(conn, base))
    if not frame.empty:
        cutoff = pd.Timestamp(datetime.now(UTC).date()) - pd.Timedelta(days=days)
        frame = frame[pd.to_datetime(frame["date"]) >= cutoff]
    return {
        "symbol": symbol,
        "underlying": base,
        "items": [
            {
                "date": str(r["date"]),
                "source": r["source"],
                "score": round(float(r["score"]), 3),
                "mentions": int(r["mentions"]),
            }
            for r in frame.to_dict("records")
        ],
    }


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
