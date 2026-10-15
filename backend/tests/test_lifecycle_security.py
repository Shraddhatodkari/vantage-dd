"""Approval lifecycle (reasons, concurrency, status consistency) and security edge cases
(expired / tampered tokens, rate limiting, safe 500s, non-member access to runs and reports)."""
from __future__ import annotations

import threading
import time

import jwt as pyjwt
import pytest
from app.core.config import get_settings
from fastapi.testclient import TestClient

from .conftest import PASSWORD, Session, deal_by, submit, wait_run


def _new_run(sess, name):
    deal = deal_by(sess, name)
    r = sess.post(f"/api/v1/deals/{deal['id']}/runs", json={})
    assert r.status_code == 202, r.text
    return deal, wait_run(sess, r.json()["id"])


def test_rejection_requires_reason_and_is_audited(analyst, partner, admin):
    deal, run = _new_run(analyst, "Yellow")
    assert run["status"] == "completed"
    submit(analyst, run["id"])
    for bad in (None, "", "   ", "no"):
        r = partner.post(f"/api/v1/runs/{run['id']}/review", json={"decision": "rejected", "note": bad})
        assert r.status_code == 422, (bad, r.text)
    assert analyst.get(f"/api/v1/runs/{run['id']}").json()["status"] == "awaiting_review"   # nothing changed
    reason = "Refinancing evidence for the 2024 maturities is missing; obtain lender correspondence."
    r = partner.post(f"/api/v1/runs/{run['id']}/review", json={"decision": "rejected", "note": reason})
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["review_note"] == reason
    # UI status matches the backend: run and deal read back with the same state the review returned
    assert analyst.get(f"/api/v1/runs/{run['id']}").json()["status"] == "rejected"
    assert analyst.get(f"/api/v1/deals/{deal['id']}").json()["status"] == "rework"
    assert partner.get(f"/api/v1/runs/{run['id']}/report").status_code == 404     # no memo for a rejected run
    events = [e for e in admin.get("/api/v1/admin/audit?limit=2000").json()
              if e["action"] == "run_rejected" and e["resource"] == f"run:{run['id']}"]
    assert len(events) == 1 and events[0]["detail"]["note"] == reason and events[0]["outcome"] == "success"


def test_concurrent_approvals_produce_exactly_one_approval(analyst):
    _, run = _new_run(analyst, "Old Dominion")
    submit(analyst, run["id"])
    reviewers = [Session("partner@vantage.dev"), Session("partner@vantage.dev")]
    codes: list[int] = []
    barrier = threading.Barrier(2)

    def approve(s):
        barrier.wait()
        codes.append(s.post(f"/api/v1/runs/{run['id']}/review", json={"decision": "approved", "note": "ok"}).status_code)

    ts = [threading.Thread(target=approve, args=(s,)) for s in reviewers]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    assert sorted(codes) == [200, 409], codes
    detail = analyst.get(f"/api/v1/runs/{run['id']}").json()
    assert detail["status"] == "approved" and len(detail["reports"]) == 1


def test_coverage_is_recorded_and_disclosed(analyst, partner):
    _, run = _new_run(analyst, "Old Dominion")
    cov = {c["agent"]: c for c in run["coverage"]}
    assert {"financial_analyst", "legal_counsel", "market_strategist", "esg_compliance", "red_team"} <= set(cov)
    cats = {k["key"]: k for k in cov["market_strategist"]["categories"]}
    assert cats["independent_market_study"]["status"] == "insufficient_evidence" and cats["independent_market_study"]["required"]
    assert cats["company_market_description"]["status"] == "reviewed_no_risk"
    assert "insufficient evidence for: Independent market or industry study" in cov["market_strategist"]["limitation"]
    assert all(c["llm"] in ("not_configured", "not_used", "no_documents") for c in cov.values())
    submit(analyst, run["id"])
    gap = [f for f in run["findings"] if f["code"] == "RED.COVERAGE_GAP.market_strategist"]
    assert gap and gap[0]["verification_status"] == "verified"
    cash = next(f for f in run["findings"] if f["code"] == "FIN.CASH_DECLINE")
    assert cash["severity"] == "low" and "net cash" in cash["detail"] and cash["verification_status"] != "rejected"
    assert partner.post(f"/api/v1/runs/{run['id']}/review", json={"decision": "approved", "note": "ok"}).status_code == 200
    memo = partner.get(f"/api/v1/runs/{run['id']}/report").json()["content_md"]
    assert "not a guarantee" in memo and "## 7. Evidence coverage and unresolved questions" in memo
    assert "Historical cut-off" in memo and "2023-02-22" in memo
    assert "stored snapshot" in memo and "| live |" not in memo


def test_rerun_does_not_duplicate_findings_or_facts(analyst):
    deal = deal_by(analyst, "Yellow")
    facts_before = analyst.get(f"/api/v1/deals/{deal['id']}/financials").json()
    _, r1 = _new_run(analyst, "Yellow")
    _, r2 = _new_run(analyst, "Yellow")
    assert r2["version"] == r1["version"] + 1
    for r in (r1, r2):
        keys = [(f["code"], f["title"]) for f in r["findings"]]
        assert len(keys) == len(set(keys))
    assert sorted((f["code"], f["severity"]) for f in r1["findings"]) == sorted((f["code"], f["severity"]) for f in r2["findings"])
    assert r1["risk_score"] == r2["risk_score"]           # deterministic
    assert analyst.get(f"/api/v1/deals/{deal['id']}/financials").json() == facts_before


def test_non_member_cannot_read_runs_or_reports(admin, analyst):
    from app.api.routes_auth import login_limiter
    admin.post("/api/v1/admin/users", json={"email": "outsider2@vantage.dev", "full_name": "Out Sider",
                                            "password": "Outsider#Pass2026", "role": "partner"})
    login_limiter.reset()
    out = TestClient(analyst.c.app)
    assert out.post("/api/v1/auth/login", json={"email": "outsider2@vantage.dev", "password": "Outsider#Pass2026"}).status_code == 200
    runs = analyst.get(f"/api/v1/deals/{deal_by(analyst, 'Old Dominion')['id']}/runs").json()
    approved = next(r for r in runs if r["status"] == "approved")
    for url in (f"/api/v1/runs/{approved['id']}", f"/api/v1/runs/{approved['id']}/report",
                f"/api/v1/runs/{approved['id']}/report.md"):
        assert out.get(url).status_code == 404, url
    h = {"X-CSRF-Token": out.cookies.get("vantage_csrf")}
    assert out.post(f"/api/v1/runs/{approved['id']}/review", json={"decision": "approved"}, headers=h).status_code == 404


def test_expired_and_tampered_tokens_are_refused(app_started):
    s = get_settings()
    now = int(time.time())
    base = {"sub": "x", "role": "partner", "type": "access", "jti": "j1"}
    expired = pyjwt.encode({**base, "iat": now - 3600, "exp": now - 60}, s.jwt_secret, algorithm=s.jwt_algorithm)
    forged = pyjwt.encode({**base, "iat": now, "exp": now + 600}, "not-the-secret-" * 3, algorithm=s.jwt_algorithm)
    c = TestClient(app_started.app)
    for tok in (expired, forged, "garbage"):
        r = c.get("/api/v1/deals", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401, tok
        assert "Traceback" not in r.text


def test_login_rate_limit_returns_429(app_started):
    from app.api.routes_auth import login_limiter
    login_limiter.reset()
    c = TestClient(app_started.app)
    codes = [c.post("/api/v1/auth/login", json={"email": "ratelimit@vantage.dev", "password": "wrong-password-1"}).status_code
             for _ in range(get_settings().login_rate_limit_per_minute + 2)]
    login_limiter.reset()
    assert codes[0] == 401 and codes[-1] == 429


def test_unhandled_error_returns_safe_500_without_trace(app_started, monkeypatch):
    import app.api.routes_auth as ra

    def boom(*a, **k):
        raise RuntimeError("secret-internal-detail /path/to/file.py")
    monkeypatch.setattr(ra, "PublicConfig", boom)
    c = TestClient(app_started.app, raise_server_exceptions=False)
    r = c.get("/api/v1/meta")
    assert r.status_code == 500 and r.json()["detail"] == "Internal error" and r.json()["request_id"]
    assert "secret-internal-detail" not in r.text and "Traceback" not in r.text


def test_logs_do_not_contain_passwords_or_tokens(app_started, caplog):
    caplog.set_level("DEBUG")
    c = TestClient(app_started.app)
    from app.api.routes_auth import login_limiter
    login_limiter.reset()
    r = c.post("/api/v1/auth/login", json={"email": "analyst@vantage.dev", "password": PASSWORD})
    assert r.status_code == 200
    c.post("/api/v1/auth/login", json={"email": "analyst@vantage.dev", "password": "Wrong#Password123"})
    login_limiter.reset()
    text = caplog.text
    assert PASSWORD not in text and "Wrong#Password123" not in text
    for cookie in ("vantage_access", "vantage_refresh"):
        val = c.cookies.get(cookie)
        if val:
            assert val not in text


@pytest.mark.parametrize("payload", [{"decision": "maybe"}, {"decision": "approved", "note": "x" * 2001}])
def test_review_payload_validation(partner, payload):
    assert partner.post("/api/v1/runs/doesnotexist/review", json=payload).status_code == 422


def test_submission_step_rules(analyst, partner):
    _, run = _new_run(analyst, "Old Dominion")
    rid = run["id"]
    assert partner.post(f"/api/v1/runs/{rid}/review", json={"decision": "approved", "note": "x"}).status_code == 409
    submit(analyst, rid)
    assert analyst.post(f"/api/v1/runs/{rid}/submit", json={}).status_code == 409          # once only
    assert analyst.post(f"/api/v1/runs/{rid}/review", json={"decision": "approved"}).status_code == 404  # no permission
    # a partner who submits a run cannot approve it either
    _, run2 = _new_run(analyst, "Old Dominion")
    submit(partner, run2["id"])
    r = partner.post(f"/api/v1/runs/{run2['id']}/review", json={"decision": "approved", "note": "x"})
    assert r.status_code == 409 and "Segregation" in r.text
    events = [e["agent"] for e in analyst.get(f"/api/v1/runs/{rid}").json()["events"]]
    assert "analyst_submission" in events
