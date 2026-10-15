# Operations guide (Windows-first, no Docker or WSL)

## Environments

| Setting | Development / demo | Production |
|---|---|---|
| `VANTAGE_ENV` | `dev` | `prod` |
| `VANTAGE_DEMO_MODE` | `true` (seeds demo users + demo deals) | **`false` — enforced; startup fails otherwise** |
| `VANTAGE_SEED_PASSWORD` | random, from `manage.py setup` | not used |
| `VANTAGE_JWT_SECRET` | random, from `manage.py setup` | ≥ 32 random characters — enforced |
| `VANTAGE_COOKIE_SECURE` | `false` (http://localhost) | **`true` — enforced** (HTTPS only) |
| `VANTAGE_CORS_ORIGINS` | localhost origins | your https origin(s) — enforced |
| `VANTAGE_SOURCE_MODE` | `snapshot` | `snapshot` or `live` |
| `VANTAGE_SEC_USER_AGENT` | optional | required for `live` ("Name email@domain") |
| `VANTAGE_DATABASE_URL` | SQLite file in `backend/` | SQLite on a backed-up disk, or Postgres |

`python scripts/manage.py check-config` validates the active configuration; the API refuses to start with an
unsafe production configuration. Secrets live only in `.env` (git-ignored) or OS environment variables; nothing
secret is compiled into the frontend (it receives only `/api/v1/meta`: environment name, demo flag and demo
account e-mails).

## First production start

```powershell
# .env (do not commit): VANTAGE_ENV=prod, VANTAGE_DEMO_MODE=false, VANTAGE_JWT_SECRET=<random>,
#                       VANTAGE_COOKIE_SECURE=true, VANTAGE_CORS_ORIGINS=["https://dd.yourfirm.com"]
.venv\Scripts\python scripts\manage.py check-config
.venv\Scripts\python scripts\manage.py migrate
.venv\Scripts\python scripts\manage.py create-admin --email admin@yourfirm.com --name "Admin Name"
.venv\Scripts\python scripts\manage.py add-real-deal --cik 716006 --fy 2022 --name "Yellow FY2022" --type credit --owner partner@yourfirm.com --member analyst@yourfirm.com --live
.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Put an HTTPS reverse proxy (IIS with ARR, or Caddy for Windows) in front of 127.0.0.1:8000. To run as a Windows
service, wrap the uvicorn command with a service manager such as NSSM. Use a single worker process:
the audit hash chain and run lock are process-local (see gaps).

## Migrations and existing databases

Schema changes go through Alembic (`backend/migrations`, current head `0004`: two-factor authentication and
password-reset tokens, additive only). A test checks that a database built from the migrations matches the models
exactly. The rules:

* **A database is never changed just by starting the app.** Before connecting, the API inspects an existing file
  read-only. A file without migration history (legacy) is refused and stays byte-identical. A file with pending
  migrations is refused unless `VANTAGE_AUTO_MIGRATE=true`. A new or empty file is created at the latest revision.
* `setup.ps1` runs `manage.py migrate --new-only`, which creates a new database and never touches an existing one.
* `manage.py migrate` applies pending migrations explicitly and **first writes a single-file backup**
  (`backups\pre-migrate-<from>-to-<to>-<UTC>-<name>.db`).
* `manage.py inspect-db --path <file>` shows tables, row counts, revision, integrity and sha256 without writing,
  and confirms the file is unchanged afterwards.
* `manage.py doctor` checks Python, required and optional packages, and that the app imports.

### Upgrading an existing database (safe procedure)

```powershell
# 1. look, don't touch
.venv\Scripts\python scripts\manage.py inspect-db --path backend\vantage.db
# 2a. legacy file (alembic_revision = null): keep it as is and start on a NEW file
#     add to .env:  VANTAGE_DATABASE_URL=sqlite:///C:/Users/<you>/.../backend/vantage-v3.db
.venv\Scripts\python scripts\manage.py migrate --new-only
# 2b. migration-managed file at an older revision: rehearse on a COPY first
copy backend\vantage_migration_test.db backend\rehearsal.db
$env:VANTAGE_DATABASE_URL = "sqlite:///$PWD/backend/rehearsal.db"
.venv\Scripts\python scripts\manage.py migrate        # writes backups\pre-migrate-... first
.venv\Scripts\python scripts\manage.py inspect-db --path backend\rehearsal.db
#     only after checking the result: point at the real file and run migrate again
```

## Backup and restore (SQLite deployments)

```powershell
.venv\Scripts\python scripts\manage.py backup             # backups\vantage-backup-<UTC>.zip
.venv\Scripts\python scripts\manage.py restore backups\vantage-backup-....zip   # stop the API first
.venv\Scripts\python scripts\manage.py verify-audit
```

`backup` uses SQLite's online backup API (read-only source, consistent while the API runs; single-file copies
without WAL sidecars) for the database and the LangGraph checkpoint store, adds document storage and the vector index, and writes a sha256 manifest. `restore` verifies every
checksum before touching anything (a tampered archive is refused) and moves the current data aside, including
`-wal`/`-shm` files, instead of deleting it. `reset-dev` also moves data aside (`backups\pre-reset-<UTC>`) and
never deletes. All of this is tested in `backend/tests/test_backup_restore.py`. Source snapshots
(`data/source_snapshots`) are content-addressed and should be backed up with the code. Postgres: use `pg_dump` /
`pg_restore` on a schedule plus the storage folders. Restore was exercised in testing (see `docs/history/ACCEPTANCE_REPORT.md`);
schedule it (Task Scheduler) and test restores regularly.

## Logs and errors

Logs are JSON lines to stdout with a request id. Request bodies, query strings, passwords and tokens are never
logged; validation errors never echo submitted values; unexpected errors return `{"detail":"Internal error",
"request_id":...}`. `/healthz`, `/readyz` and `/metrics` (Prometheus text) support monitoring.

## External sources

Live retrieval uses a 20 s timeout, at most 3 retries with exponential backoff (honouring `Retry-After`), and a
per-host rate limit (≤ 8 requests/s to SEC). Every retrieval is stored content-addressed (never overwritten) and
recorded with URL, sha256 and UTC timestamp. Snapshot mode re-verifies the sha256 before use. A failed retrieval
returns an explicit error; nothing is silently substituted.

## Account security (release 1.2)

* **Two-factor authentication:** users enable it under *Account security* (QR code or manual key for any
  authenticator app). Secrets are encrypted at rest with a key derived from `VANTAGE_JWT_SECRET`, or with
  `VANTAGE_MFA_ENCRYPTION_KEY` (a Fernet key) if set. **Rotating the JWT secret without setting that key makes
  existing enrolments unreadable**; affected users then need an administrator to reset their 2FA.
* **Mandatory 2FA for roles:** `VANTAGE_MFA_REQUIRED_ROLES=["admin","partner"]`. Users in those roles can only reach
  *Account security* until they enrol (enforced by the API, not just the UI).
* **Forgotten password:** *Administration → Users → Reset password* issues a single-use link (30 minutes,
  `VANTAGE_PASSWORD_RESET_MINUTES`). Give it to the user through a trusted channel; it is shown once and stored only
  as a hash. Using it signs out every existing session of that user. Administrators cannot reset their own password
  or 2FA from this page (another administrator must), and `manage.py create-admin` remains the break-glass path.
* **Lost phone:** *Administration → Users → Reset 2FA*; the user enrols again.
* Every step is in the audit log (`mfa_*`, `login_mfa_failed`, `password_reset_*`); secrets and tokens never are.
* **Metrics:** in production `/metrics` needs `Authorization: Bearer <VANTAGE_METRICS_TOKEN>` (404 without it).

## PostgreSQL

`pip install -r backend\requirements-postgres.txt`, then
`VANTAGE_DATABASE_URL=postgresql+psycopg://user:password@host:5432/vantage` and `manage.py migrate`. Verified in
this build on PostgreSQL 16.15: the full backend test suite passes (160), and `scripts/pg_migration_check.py`
round-trips 0001 → 0004 → 0001 → 0004 with data preserved. Run that script only against an **empty scratch database**;
it refuses a non-empty one. Back up with `pg_dump -Fc` and restore with `pg_restore`; test restores on a schedule.

## AI provider

Default: `VANTAGE_LLM_PROVIDER=offline` (rules and extractive search only). To enable Claude, set
`VANTAGE_LLM_PROVIDER=anthropic` and `VANTAGE_ANTHROPIC_API_KEY` in `.env` (never in source control). Then use
Administration → "Run connectivity check": one minimal, audited call that reports errors by type only. Cost bounds:
at most 5 LLM calls per analysis run, 2,048 output tokens per call, 60 s timeout, 2 retries; plus one call per
"Ask the documents" question. LLM output is used only after quote-location, number and citation checks.

## Dependency checks

`pip-audit -r backend\requirements.txt` and `npm audit` in `frontend`: both report 0 known vulnerabilities in release
1.2 (production and development packages). Security scans: `docs/evidence/security_scans.md`.
