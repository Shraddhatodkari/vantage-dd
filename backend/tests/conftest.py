"""Test configuration. Unit tests use mocks / fixtures; tests marked `live` hit the real SEC, GLEIF and
FRED endpoints and run only with VANTAGE_LIVE_TESTS=1."""
import os
import shutil
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="vantage-test-"))
ROOT = Path(__file__).resolve().parents[2]
os.environ.update({
    "VANTAGE_ENV": "test",
    "VANTAGE_DEMO_MODE": "true",
    "VANTAGE_SEED_PASSWORD": "Test-Demo#Passw0rd",
    # set VANTAGE_TEST_DATABASE_URL=postgresql+psycopg://... to run the suite against PostgreSQL (empty database)
    "VANTAGE_DATABASE_URL": os.getenv("VANTAGE_TEST_DATABASE_URL") or f"sqlite:///{_tmp / 'test.db'}",
    "VANTAGE_CHECKPOINT_DB": str(_tmp / "checkpoints.db"),
    "VANTAGE_VECTOR_INDEX_DIR": str(_tmp / "vec"),
    "VANTAGE_STORAGE_DIR": str(_tmp / "storage"),
    "VANTAGE_SOURCE_MODE": "snapshot",
    "VANTAGE_MLFLOW_ENABLED": "false",
    "VANTAGE_LLM_PROVIDER": "offline",
    "VANTAGE_JWT_SECRET": "test-secret-test-secret-test-secret-123456",
    "MLFLOW_DISABLE_AGENT_HINT": "1",
})

import pytest  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PASSWORD = os.environ["VANTAGE_SEED_PASSWORD"]


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits real external sources (set VANTAGE_LIVE_TESTS=1)")


def pytest_collection_modifyitems(config, items):
    if os.getenv("VANTAGE_LIVE_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="live source test: set VANTAGE_LIVE_TESTS=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def app_started():
    with TestClient(app) as c:  # runs lifespan: migrations + demo seed (from source snapshots)
        yield c
    shutil.rmtree(_tmp, ignore_errors=True)


class Session:
    """A browser-like client: cookies + CSRF header on state-changing calls."""

    def __init__(self, email: str | None = None):
        self.c = TestClient(app)
        if email:
            r = self.c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
            assert r.status_code == 200, r.text

    def _h(self):
        return {"X-CSRF-Token": self.c.cookies.get("vantage_csrf", "")}

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, **kw):
        return self.c.post(url, headers={**self._h(), **kw.pop("headers", {})}, **kw)

    def delete(self, url, **kw):
        return self.c.delete(url, headers={**self._h(), **kw.pop("headers", {})}, **kw)


@pytest.fixture(scope="session")
def analyst(app_started):
    return Session("analyst@vantage.dev")


@pytest.fixture(scope="session")
def partner(app_started):
    return Session("partner@vantage.dev")


@pytest.fixture(scope="session")
def admin(app_started):
    return Session("admin@vantage.dev")


def deal_by(session: Session, fragment: str) -> dict:
    return next(d for d in session.get("/api/v1/deals").json() if fragment in d["name"])


def wait_run(session: Session, run_id: str, timeout: float = 120) -> dict:
    import time
    t = time.time()
    while time.time() - t < timeout:
        r = session.get(f"/api/v1/runs/{run_id}").json()
        if r["status"] not in ("queued", "running"):
            return r
        time.sleep(0.3)
    raise AssertionError("run timed out")


def submit(session: Session, run_id: str, note: str = "Analysis checked; submitting for partner review.") -> dict:
    """Analyst step between a completed run and partner review."""
    r = session.post(f"/api/v1/runs/{run_id}/submit", json={"note": note})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "awaiting_review"
    return r.json()
