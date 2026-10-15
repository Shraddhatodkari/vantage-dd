"""Migration safety on disposable databases (never the user's files):
* 0001 -> head upgrade preserves existing rows and writes a pre-migration backup first,
* a second init_db is a no-op (no extra backup),
* a pre-migration (unversioned) database is refused and left byte-identical,
* append-only guards survive the upgrade."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
HEAD = max(p.name.split("_")[0] for p in (BACKEND / "migrations" / "versions").glob("0*.py"))

SCRIPT = textwrap.dedent("""
    import os, sys
    sys.path.insert(0, os.getcwd())
    from alembic import command
    from alembic.config import Config
    from app.db.session import engine
    cfg = Config("alembic.ini"); cfg.set_main_option("script_location", "migrations")
    if sys.argv[1] == "seed0001":
        with engine.begin() as cx:
            cfg.attributes["connection"] = cx
            command.upgrade(cfg, "0001")
            cx.exec_driver_sql("insert into users(id,email,full_name,hashed_password,role,is_active,is_demo_account,"
                               "failed_logins,created_at) values('u1','keep@x.io','Keep','h','analyst',1,0,0,'2026-01-01')")
            cx.exec_driver_sql("insert into deals(id,name,target_company,deal_type,sector,data_classification,"
                               "is_historical,currency,status,owner_id,created_at) values('d1','Keep deal','T','credit',"
                               "'S','synthetic',0,'USD','open','u1','2026-01-01')")
    elif sys.argv[1] == "startup":
        from app.db.seed import init_db
        init_db(allow_upgrade=False)          # what the API does at start-up by default
    else:
        from app.db.seed import init_db
        init_db()
""")


def _run(tmp: Path, step: str, db: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "VANTAGE_ENV": "test", "VANTAGE_DEMO_MODE": "false", "VANTAGE_DATABASE_URL": f"sqlite:///{db}",
           "VANTAGE_BACKUP_DIR": str(tmp / "bk"), "VANTAGE_JWT_SECRET": "m" * 40,
           "PYTHONUTF8": "1"}
    script = tmp / "mig.py"
    script.write_text(SCRIPT, encoding="utf-8")
    return subprocess.run([sys.executable, str(script), step], cwd=BACKEND, env=env, capture_output=True, text=True,
                          encoding="utf-8")


def test_upgrade_from_0001_preserves_data_and_backs_up(tmp_path):
    db = tmp_path / "m.db"
    assert _run(tmp_path, "seed0001", db).returncode == 0
    r = _run(tmp_path, "init", db)
    assert r.returncode == 0, r.stderr[-2000:]
    c = sqlite3.connect(db)
    assert c.execute("select version_num from alembic_version").fetchone()[0] == HEAD
    assert c.execute("select email from users").fetchall() == [("keep@x.io",)]
    assert c.execute("select name, historical_cutoff from deals").fetchall() == [("Keep deal", None)]
    cols = [row[1] for row in c.execute("pragma table_info(analysis_runs)")]
    assert "coverage" in cols and "submitted_by" in cols
    triggers = {row[0] for row in c.execute("select name from sqlite_master where type='trigger'")}
    assert any("audit" in t for t in triggers)
    backups = list((tmp_path / "bk").iterdir())
    assert len(backups) == 1 and backups[0].name.startswith(f"pre-migrate-0001-to-{HEAD}-")
    b = sqlite3.connect(backups[0])
    assert b.execute("select version_num from alembic_version").fetchone()[0] == "0001"
    assert b.execute("select count(*) from users").fetchone()[0] == 1
    # second start: already at head -> no new backup, data unchanged
    assert _run(tmp_path, "init", db).returncode == 0
    assert len(list((tmp_path / "bk").iterdir())) == 1


def test_unversioned_legacy_database_is_refused_untouched(tmp_path):
    db = tmp_path / "legacy.db"
    c = sqlite3.connect(db)
    c.execute("create table users(id text primary key, email text)")
    c.execute("insert into users values('x','legacy@x.io')")
    c.commit()
    c.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    r = _run(tmp_path, "init", db)
    assert r.returncode != 0 and "predates schema migrations" in r.stderr
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert not (tmp_path / "bk").exists()


def test_api_startup_refuses_pending_migration_and_leaves_db_untouched(tmp_path):
    db = tmp_path / "m.db"
    assert _run(tmp_path, "seed0001", db).returncode == 0
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    r = _run(tmp_path, "startup", db)
    assert r.returncode != 0 and "was NOT modified" in r.stderr
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert not (tmp_path / "bk").exists()


def test_models_match_migrations_exactly(tmp_path):
    """A brand-new database built only from the migrations must match the SQLAlchemy models (no drift), so a
    column added to a model without a migration (or vice versa) fails here."""
    script = tmp_path / "drift.py"
    script.write_text(textwrap.dedent("""
        import os, sys
        sys.path.insert(0, os.getcwd())
        from alembic import command
        from alembic.autogenerate import compare_metadata
        from alembic.config import Config
        from alembic.migration import MigrationContext
        from app.db.models import Base
        from app.db.session import engine
        cfg = Config("alembic.ini"); cfg.set_main_option("script_location", "migrations")
        with engine.begin() as cx:
            cfg.attributes["connection"] = cx
            command.upgrade(cfg, "head")
        with engine.connect() as cx:
            diff = compare_metadata(MigrationContext.configure(cx, opts={"compare_type": False}), Base.metadata)
        print("DIFF", repr(diff))
        sys.exit(1 if diff else 0)
    """), encoding="utf-8")
    env = {**os.environ, "VANTAGE_ENV": "test", "VANTAGE_DEMO_MODE": "false", "VANTAGE_JWT_SECRET": "m" * 40,
           "VANTAGE_DATABASE_URL": f"sqlite:///{tmp_path / 'drift.db'}", "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, str(script)], cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
