"""Tamper-evident audit trail.

* Each entry stores sha256(prev_hash || canonical entry); editing or deleting any row breaks the chain,
  which `verify_chain` detects.
* The ORM refuses UPDATE/DELETE of AuditLog rows, and database triggers (created by `install_guards`
  and by the Alembic migration) refuse them at the SQL level too.
* Limitation: someone with direct file access to the database could rewrite the whole chain. For
  stronger guarantees, ship entries to WORM storage / a SIEM (documented in docs/OPERATIONS.md).
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.db.models import AuditLog

GENESIS = "0" * 64
_lock = threading.Lock()
_SECRET_KEYS = {"password", "token", "access_token", "refresh_token", "csrf", "secret", "api_key"}


def _scrub(obj):
    if isinstance(obj, dict):
        return {k: ("[redacted]" if k.lower() in _SECRET_KEYS else _scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def _entry_hash(prev_hash: str, row: dict) -> str:
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


def _utc_iso(dt: datetime) -> str:
    # SQLite returns naive datetimes; values are always written in UTC, so never apply local time.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="microseconds")


def _canonical(e: AuditLog) -> dict:
    return {"user_id": e.user_id, "user_email": e.user_email, "action": e.action, "resource": e.resource,
            "outcome": e.outcome, "detail": e.detail, "ip": e.ip,
            "created_at": _utc_iso(e.created_at)}


def write_audit(db: Session, *, user_id: str | None, user_email: str | None, action: str, resource: str,
                outcome: str = "success", detail: dict | None = None, ip: str | None = None) -> AuditLog:
    with _lock:
        last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        prev = last.hash if last else GENESIS
        e = AuditLog(user_id=user_id, user_email=user_email, action=action, resource=resource, outcome=outcome,
                     detail=_scrub(detail or {}), ip=ip, created_at=datetime.now(timezone.utc))
        e.prev_hash = prev
        e.hash = _entry_hash(prev, _canonical(e))
        db.add(e)
        db.commit()
        return e


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    n = 0
    for e in db.query(AuditLog).order_by(AuditLog.id).yield_per(500):
        n += 1
        if e.prev_hash != prev or e.hash != _entry_hash(prev, _canonical(e)):
            return {"valid": False, "entries_checked": n, "first_invalid_id": e.id}
        prev = e.hash
    return {"valid": True, "entries_checked": n, "head": prev}


@event.listens_for(AuditLog, "before_update")
def _no_update(*_):
    raise PermissionError("audit_log is append-only")


@event.listens_for(AuditLog, "before_delete")
def _no_delete(*_):
    raise PermissionError("audit_log is append-only")


SQLITE_TRIGGERS = [
    "CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log "
    "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;",
    "CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log "
    "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;",
    "CREATE TRIGGER IF NOT EXISTS report_versions_no_update BEFORE UPDATE ON report_versions "
    "BEGIN SELECT RAISE(ABORT, 'approved reports are immutable'); END;",
    "CREATE TRIGGER IF NOT EXISTS report_versions_no_delete BEFORE DELETE ON report_versions "
    "BEGIN SELECT RAISE(ABORT, 'approved reports are immutable'); END;",
]
POSTGRES_TRIGGERS = [
    """CREATE OR REPLACE FUNCTION vantage_append_only() RETURNS trigger AS $$
       BEGIN
         IF TG_TABLE_NAME = 'report_versions' THEN RAISE EXCEPTION 'approved reports are immutable'; END IF;
         RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
       END; $$ LANGUAGE plpgsql;""",
    "DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log;",
    "CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log "
    "FOR EACH ROW EXECUTE FUNCTION vantage_append_only();",
    "DROP TRIGGER IF EXISTS report_versions_append_only ON report_versions;",
    "CREATE TRIGGER report_versions_append_only BEFORE UPDATE OR DELETE ON report_versions "
    "FOR EACH ROW EXECUTE FUNCTION vantage_append_only();",
]


def install_guards(connection) -> None:
    stmts = SQLITE_TRIGGERS if connection.dialect.name == "sqlite" else POSTGRES_TRIGGERS
    for s in stmts:
        connection.execute(text(s))
