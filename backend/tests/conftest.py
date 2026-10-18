import os
from collections.abc import Iterator

import pandas as pd
import pytest
from sqlalchemy import Engine, text

from app.db.engine import make_engine
from app.db.schema import metadata

TEST_DB = os.environ.get("TEST_DATABASE_URL")


def ohlcv(index: pd.DatetimeIndex, closes: list[float]) -> pd.DataFrame:
    close = pd.Series(closes, index=index, dtype="float64")
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1.0,
        },
        index=index,
    )


@pytest.fixture
def engine() -> Iterator[Engine]:
    if not TEST_DB:
        pytest.skip("TEST_DATABASE_URL non impostata")
    eng = make_engine(TEST_DB)
    with eng.begin() as conn:
        conn.execute(
            text(
                "DROP TABLE IF EXISTS trades, trade_ideas, signals, sentiment, indicators, prices, "
                "instruments, alembic_version CASCADE"
            )
        )
    metadata.create_all(eng)
    yield eng
    metadata.drop_all(eng)
    eng.dispose()
