"""Backup / restore / inspect-db / reset-dev through the real CLI, on a disposable environment only."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _cli(tmp: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "VANTAGE_ENV": "test", "VANTAGE_DEMO_MODE": "false",
           "VANTAGE_DATABASE_URL": f"sqlite:///{tmp / 'app.db'}", "VANTAGE_CHECKPOINT_DB": str(tmp / "cp.db"),
           "VANTAGE_STORAGE_DIR": str(tmp / "st"), "VANTAGE_VECTOR_INDEX_DIR": str(tmp / "vec"),
           "VANTAGE_BACKUP_DIR": str(tmp / "bk"), "VANTAGE_JWT_SECRET": "b" * 40, "VANTAGE_MLFLOW_ENABLED": "false",
           "PYTHONUTF8": "1"}   # same output encoding on Windows and Linux
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "manage.py"), *args], env=env, cwd=tmp,
                          capture_output=True, text=True, encoding="utf-8", input=stdin)


def _users(db: Path) -> list:
    c = sqlite3.connect(db)
    try:
        return c.execute("select email from users order by email").fetchall()
    finally:
        c.close()


def test_backup_restore_roundtrip(tmp_path):
    assert _cli(tmp_path, "migrate").returncode == 0
    db = tmp_path / "app.db"
    c = sqlite3.connect(db)
    c.execute("insert into users(id,email,full_name,hashed_password,role,is_active,is_demo_account,failed_logins,"
              "created_at) values('u1','before@x.io','B','h','analyst',1,0,0,'2026-01-01')")
    c.commit()
    c.close()
    (tmp_path / "st").mkdir()
    (tmp_path / "st" / "doc.txt").write_text("stored document", encoding="utf-8")

    r = _cli(tmp_path, "backup")
    assert r.returncode == 0, r.stdout + r.stderr
    archive = next((tmp_path / "bk").glob("vantage-backup-*.zip"))
    names = zipfile.ZipFile(archive).namelist()
    assert "app.db" in names and "st/doc.txt" in names and "backup_manifest.json" in names
    assert not any(n.endswith(("-wal", "-shm")) for n in names)

    # change data after the backup, then restore
    c = sqlite3.connect(db)
    c.execute("update users set email='after@x.io'")
    c.commit()
    c.close()
    r = _cli(tmp_path, "restore", str(archive), "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _users(db) == [("before@x.io",)]
    assert (tmp_path / "st" / "doc.txt").read_text(encoding="utf-8") == "stored document"
    aside = next((tmp_path / "bk").glob("pre-restore-*"))
    assert _users(aside / "app.db") == [("after@x.io",)]          # previous data kept, not deleted
    assert _cli(tmp_path, "verify-audit").returncode == 0


def test_restore_rejects_tampered_archive(tmp_path):
    assert _cli(tmp_path, "migrate").returncode == 0
    assert _cli(tmp_path, "backup").returncode == 0
    archive = next((tmp_path / "bk").glob("vantage-backup-*.zip"))
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(tampered, "w") as dst:
        for n in src.namelist():
            data = src.read(n)
            dst.writestr(n, data + b"x" if n == "app.db" else data)
    before = hashlib.sha256((tmp_path / "app.db").read_bytes()).hexdigest()
    r = _cli(tmp_path, "restore", str(tampered), "--yes")
    assert r.returncode == 2 and "integrity check failed" in r.stdout
    assert hashlib.sha256((tmp_path / "app.db").read_bytes()).hexdigest() == before


def test_inspect_db_is_read_only(tmp_path):
    legacy = tmp_path / "legacy.db"
    c = sqlite3.connect(legacy)
    c.execute("create table users(id text, email text)")
    c.execute("insert into users values('1','x@y.z')")
    c.commit()
    c.close()
    before = hashlib.sha256(legacy.read_bytes()).hexdigest()
    r = _cli(tmp_path, "inspect-db", "--path", str(legacy))
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout)
    assert info["row_counts"] == {"users": 1} and info["alembic_revision"] is None
    assert info["unchanged_after_inspection"] is True and info["integrity"] == "ok"
    assert hashlib.sha256(legacy.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["legacy.db"]   # no -wal/-shm created


def test_reset_dev_moves_aside_never_deletes(tmp_path):
    assert _cli(tmp_path, "migrate").returncode == 0
    r = _cli(tmp_path, "reset-dev", "--yes")
    assert r.returncode == 0, r.stdout
    assert not (tmp_path / "app.db").exists()
    aside = next((tmp_path / "bk").glob("pre-reset-*"))
    assert (aside / "app.db").exists()


def test_migrate_new_only_never_touches_existing_database(tmp_path):
    db = tmp_path / "app.db"
    c = sqlite3.connect(db)
    c.execute("create table users(id text, email text)")
    c.commit()
    c.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    r = _cli(tmp_path, "migrate", "--new-only")
    assert r.returncode == 0 and "left untouched" in r.stdout
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    r = _cli(tmp_path, "migrate")                      # explicit migrate still refuses an unversioned DB
    assert r.returncode == 2 and "REFUSED" in r.stdout
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
