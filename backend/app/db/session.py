from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()
_connect_args = {"check_same_thread": False, "timeout": 30} if _settings.is_sqlite else {}
engine = create_engine(_settings.database_url, connect_args=_connect_args, pool_pre_ping=True)

if _settings.is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")      # enforce referential integrity
        cur.execute("PRAGMA journal_mode=WAL")     # readers don't block the analysis worker
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
