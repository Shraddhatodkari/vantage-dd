from alembic import context
from app.core.config import get_settings
from app.db import models  # noqa: F401  (register tables)
from app.db.session import Base, engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = context.config.attributes.get("connection") or engine
    if hasattr(connectable, "connect") and not hasattr(connectable, "dialect_name"):
        with connectable.connect() as connection:
            _run(connection)
    else:
        _run(connectable)


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata,
                      render_as_batch=get_settings().is_sqlite)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
