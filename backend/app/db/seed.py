"""Database initialisation and DEMO-ONLY seeding.

Seeding runs only when VANTAGE_DEMO_MODE=true (refused in prod). Demo accounts take their password
from VANTAGE_SEED_PASSWORD — nothing is hard-coded. Illustrative deals are labelled as synthetic;
real deals are built from the stored SEC/GLEIF/FRED source snapshot (or live, if configured).
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.analytics.financials import store_csv_facts
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.audit import install_guards, write_audit
from app.db.models import Deal, DealMember, Document, User
from app.db.session import SessionLocal, engine
from app.rag.ingest import ingest_text

log = logging.getLogger("vantage.seed")

DEMO_USERS = [("admin@vantage.dev", "Aisha Admin", "admin"), ("partner@vantage.dev", "Priya Partner", "partner"),
              ("analyst@vantage.dev", "Arjun Analyst", "analyst")]
ILLUSTRATIVE = [
    {"folder": "northwind", "name": "Project Northwind (illustrative)", "target_company": "Northwind Logistics (fictional)",
     "deal_type": "m_and_a", "sector": "Transportation & Logistics", "deal_size_musd": 420.0},
    {"folder": "helios", "name": "Project Helios (illustrative)", "target_company": "Helios Payments (fictional)",
     "deal_type": "vendor_risk", "sector": "Payments / Fintech", "deal_size_musd": 380.0},
]
REAL = [  # (CIK, fiscal year, deal name, type, sector)
    ("716006", 2022, "Yellow Corporation — FY2022 credit review", "credit", "Trucking (LTL)"),
    ("878927", 2022, "Old Dominion Freight Line — FY2022 credit review", "credit", "Trucking (LTL)"),
    # blind benchmark (pre-registered in ml/eval/golden.json before their data was loaded)
    ("1592058", 2021, "Party City Holdco — FY2021 credit review", "credit", "Specialty retail"),
    ("28823", 2022, "Diebold Nixdorf — FY2022 credit review", "credit", "ATM & retail technology"),
    ("1177702", 2022, "Saia — FY2022 credit review", "credit", "Trucking (LTL)"),
]


def _sqlite_path():
    from pathlib import Path
    s = get_settings()
    if not s.is_sqlite:
        return None
    p = Path(s.database_url.replace("sqlite:///", "", 1))
    return p if p.exists() else None


def inspect_sqlite_readonly(path) -> dict:
    """Open a SQLite file strictly read-only (no WAL switch, no writes) and describe it."""
    import sqlite3
    from pathlib import Path
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    cx = sqlite3.connect(uri, uri=True)
    try:
        tables = [r[0] for r in cx.execute("select name from sqlite_master where type='table' order by name")]
        rev = cx.execute("select version_num from alembic_version").fetchone()[0] if "alembic_version" in tables else None
        # table names come from the inspected file itself (read-only connection); quote them as SQL identifiers
        counts = {t: cx.execute('select count(*) from "{}"'.format(t.replace('"', '""'))).fetchone()[0]  # nosec B608
                  for t in tables if not t.startswith("sqlite_")}
        integrity = cx.execute("pragma integrity_check").fetchone()[0]
        journal = cx.execute("pragma journal_mode").fetchone()[0]
    finally:
        cx.close()
    return {"tables": tables, "alembic_revision": rev, "row_counts": counts, "integrity": integrity, "journal_mode": journal}


def _pre_migration_backup(src, current: str, head: str) -> str:
    """Online, consistent single-file copy of the database before pending migrations are applied."""
    import sqlite3
    from datetime import datetime, timezone
    s = get_settings()
    s.backup_dir.mkdir(parents=True, exist_ok=True)
    dst = s.backup_dir / f"pre-migrate-{current}-to-{head}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{src.name}"
    a = sqlite3.connect(src.resolve().as_uri() + "?mode=ro", uri=True)
    b = sqlite3.connect(dst)
    try:
        a.backup(b)
        b.execute("pragma journal_mode=DELETE")   # self-contained file, no -wal/-shm sidecars
    finally:
        b.close()
        a.close()
    log.warning("pre-migration backup written to %s", dst)
    return str(dst)


def init_db(allow_upgrade: bool = True) -> None:
    """Bring the schema to the latest Alembic revision (idempotent) and (re)install append-only guards.
    * An existing database is first inspected strictly read-only. One that predates migrations is refused and
      left byte-for-byte untouched.
    * Before pending migrations are applied to an existing SQLite file, a backup copy is written.
    * allow_upgrade=False (API start-up unless VANTAGE_AUTO_MIGRATE=true): an existing database with pending
      migrations is refused; apply them explicitly with `manage.py migrate` after testing on a copy."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    backend = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "migrations"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    src = _sqlite_path()
    if src is not None and src.stat().st_size > 0:
        info = inspect_sqlite_readonly(src)
        if "users" in info["tables"] and info["alembic_revision"] is None:
            raise RuntimeError(
                "This database predates schema migrations and will NOT be modified. Point VANTAGE_DATABASE_URL to a "
                "new database file (your existing file stays untouched), or inspect it read-only with "
                "`python scripts/manage.py inspect-db --path <file>`.")
        if info["alembic_revision"] and info["alembic_revision"] != head:
            if not allow_upgrade:
                raise RuntimeError(
                    f"Database is at schema revision {info['alembic_revision']}; this version needs {head}. It was NOT "
                    "modified. Test the upgrade on a copy, then run `python scripts/manage.py migrate` (it writes a "
                    "backup first), or set VANTAGE_AUTO_MIGRATE=true.")
            _pre_migration_backup(src, info["alembic_revision"], head)
    with engine.begin() as cx:
        cfg.attributes["connection"] = cx
        command.upgrade(cfg, "head")
        install_guards(cx)


def seed_demo(db: Session | None = None) -> dict:
    s = get_settings()
    if not s.demo_mode or s.env == "prod":
        return {"seeded": False, "reason": "demo mode disabled"}
    own = db is None
    db = db or SessionLocal()
    result = {"seeded": True, "users": 0, "illustrative": 0, "real": [], "errors": []}
    try:
        users = {}
        for email, name, role in DEMO_USERS:
            u = db.query(User).filter_by(email=email).first()
            if not u:
                u = User(email=email, full_name=name, role=role, hashed_password=hash_password(s.seed_password),
                         is_demo_account=True)
                db.add(u)
                db.flush()
                result["users"] += 1
            users[role] = u
        team = [users["analyst"].id, users["partner"].id]  # admin is deliberately NOT a member
        for d in ILLUSTRATIVE:
            if db.query(Deal).filter_by(name=d["name"]).first():
                continue
            deal = Deal(**{k: v for k, v in d.items() if k != "folder"}, owner_id=users["analyst"].id,
                        data_classification="illustrative",
                        deal_size_basis="Illustrative figure for a fictional company (synthetic demo data)")
            db.add(deal)
            db.flush()
            for uid in team:
                db.add(DealMember(deal_id=deal.id, user_id=uid, added_by=users["analyst"].id))
            for p in sorted((s.sample_data_dir / d["folder"]).iterdir()):
                if p.suffix not in (".txt", ".csv"):
                    continue
                text = p.read_text(encoding="utf-8")
                if p.suffix == ".csv":
                    store_csv_facts(db, deal, text, p.name)
                doc_id = uuid.uuid4().hex
                res = ingest_text(deal.id, doc_id, p.name, text, doc_type="financials" if p.suffix == ".csv" else None)
                db.add(Document(id=doc_id, deal_id=deal.id, filename=p.name, doc_type=res.doc_type, sha256=res.sha256,
                                n_chars=res.n_chars, n_chunks=res.n_chunks, pii_redactions=res.redactions,
                                injection_flags=len(res.injection_hits), data_classification="illustrative",
                                uploaded_by=users["analyst"].id))
            result["illustrative"] += 1
        db.commit()
        from app.sources.http import SourceUnavailable
        from app.sources.real_deals import build_real_deal
        for cik, fy, name, dtype, sector in REAL:
            if db.query(Deal).filter_by(name=name).first():
                continue
            try:
                rep = build_real_deal(db, cik=cik, fiscal_year=fy, name=name, deal_type=dtype, sector=sector,
                                      owner_id=users["analyst"].id, member_ids=team)
                db.commit()
                result["real"].append({"deal": name, "facts": rep.facts_written, "documents": rep.documents_added,
                                       "missing": rep.facts_missing, "warnings": rep.warnings})
            except SourceUnavailable as exc:
                db.rollback()
                result["errors"].append(f"{name}: {exc}")
                log.warning("real deal %s not built: %s", name, exc)
        write_audit(db, user_id=None, user_email="system", action="demo_seed", resource="database",
                    detail={k: v for k, v in result.items() if k != "seeded"})
        return result
    finally:
        if own:
            db.close()
