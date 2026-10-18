from collections.abc import Iterator

from sqlalchemy import Connection

from app.db.engine import get_engine


def get_conn() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        yield conn
