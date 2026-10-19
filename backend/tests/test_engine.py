from collections.abc import Iterator

import pytest

from app.config import get_settings
from app.db.engine import get_migration_engine, make_engine

POOLED = "postgresql://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"
DIRECT = "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require"


@pytest.fixture(autouse=True)
def _fresh_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.chdir("/")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_make_engine_uses_psycopg() -> None:
    assert make_engine(POOLED).url.drivername == "postgresql+psycopg"
    assert make_engine("postgres://u:p@h/db").url.drivername == "postgresql+psycopg"


def test_migrations_prefer_direct_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", POOLED)
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", DIRECT)
    assert get_migration_engine().url.host == "ep-x.eu-central-1.aws.neon.tech"


def test_migrations_fall_back_to_pooled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", POOLED)
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", "")
    assert get_migration_engine().url.host == "ep-x-pooler.eu-central-1.aws.neon.tech"


def test_migrations_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_UNPOOLED", raising=False)
    with pytest.raises(RuntimeError):
        get_migration_engine()
