from functools import lru_cache

from sqlalchemy import Engine, create_engine

from app.config import get_settings


def make_engine(url: str) -> Engine:
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url is None:
        raise RuntimeError("DATABASE_URL non impostata")
    return make_engine(url.get_secret_value())


def get_migration_engine() -> Engine:
    """Connessione diretta (senza PgBouncer) per le migrazioni; ripiega su DATABASE_URL."""
    settings = get_settings()
    for url in (settings.database_url_unpooled, settings.database_url):
        if url is not None and url.get_secret_value():
            return make_engine(url.get_secret_value())
    raise RuntimeError("DATABASE_URL non impostata")
