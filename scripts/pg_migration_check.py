"""Migration round-trip on an EMPTY PostgreSQL database you name (never point it at a database with real data):
upgrade 0001 -> insert rows -> upgrade head -> downgrade 0001 -> upgrade head, checking rows survive each step.

    python scripts/pg_migration_check.py postgresql+psycopg://user@host:5432/empty_scratch_db
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if len(sys.argv) != 2 or not sys.argv[1].startswith("postgresql"):
    sys.exit("usage: python scripts/pg_migration_check.py postgresql+psycopg://user@host:5432/EMPTY_scratch_db")
os.environ.update(VANTAGE_ENV="test", VANTAGE_DATABASE_URL=sys.argv[1], VANTAGE_JWT_SECRET="m" * 40)
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.db.session import engine  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402


def check(cond: object, msg: object = "verification check failed") -> None:
    """Explicit check (unlike `assert`, never removed by `python -O`): a verification script must not pass silently."""
    if not cond:
        raise SystemExit(f"CHECK FAILED: {msg}")


cfg = Config("alembic.ini")
cfg.set_main_option("script_location", "migrations")


def run(fn, rev):
    with engine.begin() as cx:
        cfg.attributes["connection"] = cx
        fn(cfg, rev)


with engine.connect() as cx:
    if inspect(cx).get_table_names():
        sys.exit("Refusing: the database is not empty. Use a scratch database.")
run(command.upgrade, "0001")
with engine.begin() as cx:
    cx.execute(text("insert into users(id,email,full_name,hashed_password,role,is_active,is_demo_account,failed_logins,"
                    "created_at) values('u1','keep@x.io','K','h','analyst',true,false,0,now())"))
    cx.execute(text("insert into companies(id,name,tickers,lei_record,created_at) values('c1','Co','[]','{}',now())"))
run(command.upgrade, "head")
with engine.begin() as cx:
    cx.execute(text("update companies set lei_match='jurisdiction_mismatch' where id='c1'"))
    head = cx.execute(text("select version_num from alembic_version")).scalar()
run(command.downgrade, "0001")
with engine.begin() as cx:
    check(cx.execute(text("select count(*) from users")).scalar() == 1)
    check(cx.execute(text("select lei_match from companies")).scalar() == "jurisdiction_mismatch")
run(command.upgrade, "head")
print(f"OK: 0001 -> {head} -> 0001 -> {head}, rows preserved")
