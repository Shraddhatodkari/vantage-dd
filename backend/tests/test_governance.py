"""Permission matrix, deal isolation, segregation of duties, audit immutability, report versions."""
import pytest
from app.core.permissions import MATRIX, Perm
from app.core.security import Role
from app.db.session import engine
from sqlalchemy import text

from .conftest import deal_by, submit, wait_run


def test_matrix_has_no_role_inheritance():
    assert Perm.RUN_REVIEW in MATRIX[Role.PARTNER]
    assert Perm.RUN_REVIEW not in MATRIX[Role.ADMIN] and Perm.RUN_REVIEW not in MATRIX[Role.ANALYST]
    assert Perm.USER_MANAGE not in MATRIX[Role.PARTNER] and Perm.DEAL_READ not in MATRIX[Role.ADMIN]


def test_admin_sees_metadata_only_not_evidence(admin, analyst):
    meta = admin.get("/api/v1/admin/deals").json()
    assert meta and set(meta[0]) == {"id", "name", "data_classification", "status", "created_at"}
    deal_id = deal_by(analyst, "Yellow")["id"]
    assert admin.get(f"/api/v1/deals/{deal_id}").status_code == 404
    assert admin.get(f"/api/v1/deals/{deal_id}/financials").status_code == 404


def test_analyst_cannot_read_audit_or_manage_users(analyst):
    assert analyst.get("/api/v1/admin/audit").status_code == 403
    assert analyst.post("/api/v1/admin/users", json={}).status_code in (403, 422)


def test_non_member_cannot_see_deal(admin, analyst):
    admin.post("/api/v1/admin/users", json={"email": "outsider@vantage.dev", "full_name": "Out Sider",
                                            "password": "Outsider#Pass2026", "role": "partner"})
    from app.api.routes_auth import login_limiter

    from .conftest import Session
    login_limiter.reset()
    s = Session()
    r = s.c.post("/api/v1/auth/login", json={"email": "outsider@vantage.dev", "password": "Outsider#Pass2026"})
    assert r.status_code == 200
    deal_id = deal_by(analyst, "Yellow")["id"]
    assert s.get(f"/api/v1/deals/{deal_id}").status_code == 404
    assert all(d["id"] != deal_id for d in s.get("/api/v1/deals").json())


def test_verified_real_deal_rejects_manual_uploads(analyst):
    deal_id = deal_by(analyst, "Yellow")["id"]
    r = analyst.post(f"/api/v1/deals/{deal_id}/documents", files={"file": ("x.txt", b"hello world text", "text/plain")})
    assert r.status_code == 409


def test_approval_rules_segregation_and_versioned_immutable_report(analyst, partner, admin):
    deal = deal_by(analyst, "Old Dominion")
    run = wait_run(analyst, analyst.post(f"/api/v1/deals/{deal['id']}/runs", json={}).json()["id"])
    assert run["status"] == "completed"
    submit(analyst, run["id"])
    # analyst cannot approve; admin cannot approve (not a business approver, not a member)
    assert analyst.post(f"/api/v1/runs/{run['id']}/review", json={"decision": "approved"}).status_code == 404
    assert admin.post(f"/api/v1/runs/{run['id']}/review", json={"decision": "approved"}).status_code == 404
    # a partner who started a run cannot approve it
    run2 = wait_run(partner, partner.post(f"/api/v1/deals/{deal['id']}/runs", json={}).json()["id"])
    submit(partner, run2["id"])
    r = partner.post(f"/api/v1/runs/{run2['id']}/review", json={"decision": "approved"})
    assert r.status_code == 409 and "Segregation" in r.text
    # proper approval
    r = partner.post(f"/api/v1/runs/{run['id']}/review", json={"decision": "approved", "note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    rep = partner.get(f"/api/v1/runs/{run['id']}/report").json()
    assert rep["version"] == 1 and rep["approved_by"] == "partner@vantage.dev"
    exp = partner.get(f"/api/v1/runs/{run['id']}/report.md")
    assert exp.text == rep["content_md"] and exp.headers["x-content-sha256"] == rep["content_sha256"]
    # second review of the same run is refused
    assert partner.post(f"/api/v1/runs/{run['id']}/review",
                        json={"decision": "rejected", "note": "second review attempt"}).status_code == 409
    # approved report rows are immutable at the database level
    with pytest.raises(Exception, match="immutable"):
        with engine.begin() as cx:
            cx.execute(text("UPDATE report_versions SET content_md='changed'"))


def test_audit_log_is_append_only_and_chain_verifies(admin):
    with pytest.raises(Exception, match="append-only"):
        with engine.begin() as cx:
            cx.execute(text("DELETE FROM audit_log"))
    with pytest.raises(Exception, match="append-only"):
        with engine.begin() as cx:
            cx.execute(text("UPDATE audit_log SET action='x'"))
    v = admin.get("/api/v1/admin/audit/verify").json()
    assert v["valid"] and v["entries_checked"] > 5
    actions = {e["action"] for e in admin.get("/api/v1/admin/audit?limit=2000").json()}
    assert {"login_success", "login_failed", "run_started", "run_approved", "demo_seed"} <= actions


def test_permission_denials_are_audited(admin, analyst):
    analyst.get("/api/v1/admin/audit")
    denials = [e for e in admin.get("/api/v1/admin/audit?limit=2000").json() if e["action"] == "permission_denied"]
    assert denials and denials[0]["outcome"] == "denied"
