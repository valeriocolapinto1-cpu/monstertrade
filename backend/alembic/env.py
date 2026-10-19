from logging.config import fileConfig

from alembic import context
from app.db.engine import get_migration_engine
from app.db.schema import metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection") or get_migration_engine()
    if hasattr(connectable, "connect"):
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(connection=connectable, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Modalità offline non supportata: serve DATABASE_URL")
run_migrations_online()
