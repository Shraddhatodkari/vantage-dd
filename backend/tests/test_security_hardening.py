"""Release 1.2 hardening found by the Bandit scan."""
from __future__ import annotations

import hashlib
import pickle
import sqlite3


class _Boom:
    """Unpickling this object would create a marker file: proof that code ran."""
    def __init__(self, marker):
        self.marker = marker

    def __reduce__(self):
        return (open, (self.marker, "w"))


def _reload(monkeypatch, path):
    from app.tools import clauses
    monkeypatch.setattr(clauses, "MODEL_PATH", path)
    monkeypatch.setenv("VANTAGE_CLAUSE_MODEL", "baseline")
    clauses._load_model.cache_clear()
    try:
        return clauses._load_model()
    finally:
        clauses._load_model.cache_clear()


def test_shipped_clause_model_matches_its_pinned_hash():
    from app.tools import clauses
    pin = clauses.MODEL_PATH.with_name(clauses.MODEL_PATH.name + ".sha256").read_text(encoding="utf-8").strip()
    assert hashlib.sha256(clauses.MODEL_PATH.read_bytes()).hexdigest() == pin
    clauses._load_model.cache_clear()
    assert clauses._load_model() is not None


def test_tampered_or_unpinned_pickle_is_never_unpickled(tmp_path, monkeypatch):
    marker = tmp_path / "code-ran"
    evil = tmp_path / "clause_classifier.pkl"
    evil.write_bytes(pickle.dumps(_Boom(str(marker))))
    assert _reload(monkeypatch, evil) is None and not marker.exists()          # no .sha256 pin -> refused
    (tmp_path / "clause_classifier.pkl.sha256").write_text("0" * 64, encoding="utf-8")
    assert _reload(monkeypatch, evil) is None and not marker.exists()          # wrong pin -> refused


def test_readonly_inspection_quotes_hostile_table_names(tmp_path):
    from app.db.seed import inspect_sqlite_readonly
    db = tmp_path / "odd.db"
    cx = sqlite3.connect(db)
    cx.execute('create table "we""ird" (x int)')
    cx.execute('insert into "we""ird" values (1)')
    cx.commit()
    cx.close()
    before = db.read_bytes()
    info = inspect_sqlite_readonly(db)
    assert info["row_counts"]['we"ird'] == 1 and db.read_bytes() == before


def test_production_hides_docs_and_api_schema():
    import os
    import subprocess
    import sys
    from pathlib import Path
    env = {**os.environ, "VANTAGE_ENV": "prod", "VANTAGE_DEMO_MODE": "false", "VANTAGE_COOKIE_SECURE": "true",
           "VANTAGE_JWT_SECRET": "p" * 48, "PYTHONUTF8": "1"}
    code = "import app.main as m; print(m.app.docs_url, m.app.openapi_url)"
    r = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "None None"


def test_unknown_paths_are_404_not_the_app_shell(app_started):
    from app.main import _DIST, app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    for p in ("/api/v1/deals//nope", "/api/v1/nope", "/._darcs", "/.git/config", "/backup.zip", "/.env"):
        r = c.get(p)
        assert r.status_code == 404 and "<html" not in r.text.lower(), p
    if _DIST.exists():                                   # client-side routes still load the app
        for p in ("/", "/deals", "/deals/abc123", "/account", "/reset-password", "/compare", "/audit", "/login"):
            r = c.get(p)
            assert r.status_code == 200 and "<div id=\"root\">" in r.text, p
        r = c.get("/BitKeeper")                          # not an app route: shell (app redirects) but status 404
        assert r.status_code == 404


def test_security_headers_have_no_unsafe_inline(app_started):
    from app.main import app
    from fastapi.testclient import TestClient
    h = TestClient(app).get("/healthz").headers
    csp = h["content-security-policy"]
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    for d in ("object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'"):
        assert d in csp
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and "permissions-policy" in h


def test_metrics_endpoint_is_not_public_in_production():
    import os
    import subprocess
    import sys
    from pathlib import Path
    code = ("from fastapi.testclient import TestClient; import app.main as m; c = TestClient(m.app); "
            "print(c.get('/metrics').status_code, c.get('/metrics', headers={'Authorization': 'Bearer wrong'}).status_code, "
            "c.get('/metrics', headers={'Authorization': 'Bearer scrape-token-123'}).status_code)")
    env = {**os.environ, "VANTAGE_ENV": "prod", "VANTAGE_DEMO_MODE": "false", "VANTAGE_COOKIE_SECURE": "true",
           "VANTAGE_JWT_SECRET": "p" * 48, "VANTAGE_METRICS_TOKEN": "scrape-token-123", "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "404 404 200"


def test_placeholder_or_weak_secrets_are_refused():
    """A value copied from documentation (e.g. 'REPLACE_WITH_...') is public: the app must refuse to run with it."""
    import pytest
    from app.core.config import ConfigError, Settings, validate_settings
    good = {"env": "dev", "demo_mode": True, "jwt_secret": "k" * 20 + "Q9_r" * 8, "seed_password": "Rand0m#Local-pw"}
    validate_settings(Settings(**good))                                        # what manage.py setup produces
    for env in ("dev", "prod"):
        with pytest.raises(ConfigError, match="placeholder"):
            validate_settings(Settings(**{**good, "env": env, "demo_mode": env == "dev", "cookie_secure": True,
                                          "jwt_secret": "REPLACE_WITH_A_LONG_RANDOM_LOCAL_SECRET"}))
    with pytest.raises(ConfigError, match="placeholder"):
        validate_settings(Settings(**{**good, "seed_password": "REPLACE_WITH_A_UNIQUE_LOCAL_DEMO_PASSWORD"}))
    for weak in ("alllowercaseletters", "NoDigitsOrSymbols", "short#1A"):
        with pytest.raises(ConfigError, match="VANTAGE_SEED_PASSWORD must be"):
            validate_settings(Settings(**{**good, "seed_password": weak}))


def test_env_example_has_no_values_for_secrets_and_is_clean_utf8():
    from pathlib import Path

    from dotenv import dotenv_values
    p = Path(__file__).resolve().parents[2] / ".env.example"
    text = p.read_bytes().decode("utf-8")                                        # strict: fails on broken encoding
    assert "Ã" not in text and "â€" not in text
    vals = dotenv_values(p)
    assert not vals.get("VANTAGE_JWT_SECRET") and not vals.get("VANTAGE_SEED_PASSWORD")
    assert not vals.get("VANTAGE_SEC_USER_AGENT")                               # no comment text read as a value
    assert all(not (v or "").lstrip().startswith("#") for v in vals.values())
