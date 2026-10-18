from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection

from app.db.engine import get_engine


def get_conn() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        yield conn


@contextmanager
def connection() -> Iterator[Connection]:
    """Connessione fuori dall'iniezione di FastAPI; nei test si sostituisce get_conn."""
    yield from _override_or_default()


def _override_or_default() -> Iterator[Connection]:
    from app.main import app

    factory = app.dependency_overrides.get(get_conn, get_conn)
    yield from factory()
