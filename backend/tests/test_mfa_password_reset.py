"""Two-factor authentication (TOTP) and administrator-issued password reset.

Every test creates its own users through the admin API, so the shared demo accounts are never changed."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import pytest
from app.core import mfa
from app.core.config import get_settings

from .conftest import Session

NEW_PW = "Fresh-Passw0rd!x"


@pytest.fixture
def clock(monkeypatch):
    """Controllable TOTP time step, so replay protection can be tested without waiting 30 seconds."""
    state = {"step": mfa.current_step()}
    monkeypatch.setattr(mfa, "current_step", lambda now=None: state["step"])
    return state


def _new_user(admin, role="analyst", password=None) -> tuple[dict, str]:
    pw = password or f"Init-{secrets.token_hex(4)}!A1"
    email = f"u{secrets.token_hex(5)}@vantage.dev"
    r = admin.post("/api/v1/admin/users", json={"email": email, "full_name": "Test User", "role": role, "password": pw})
    assert r.status_code == 201, r.text
    return r.json(), pw


def _login(email, pw) -> tuple[Session, object]:
    s = Session()
    return s, s.c.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _enrol(s: Session, clock) -> str:
    r = s.post("/api/v1/auth/mfa/setup")
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]
    assert r.json()["otpauth_uri"].startswith("otpauth://totp/") and "<svg" in r.json()["qr_svg"]
    assert s.post("/api/v1/auth/mfa/enable", json={"code": "000000" if mfa.hotp(secret, clock["step"]) != "000000"
                                                   else "111111"}).status_code == 422
    assert s.post("/api/v1/auth/mfa/enable", json={"code": mfa.hotp(secret, clock["step"])}).status_code == 200
    return secret


def test_totp_matches_rfc6238_reference_vectors():
    """RFC 6238 appendix B (SHA-1 key "12345678901234567890"), last 6 of the 8-digit reference values."""
    key = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    for t, ref in [(59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"), (1234567890, "89005924"),
                   (2000000000, "69279037")]:
        assert mfa.hotp(key, t // 30) == ref[-6:]
        assert mfa.verify_code(key, ref[-6:], None, now=t) == t // 30
    assert mfa.verify_code(key, "94287082"[-6:], 59 // 30, now=59) is None          # same step twice: replay
    assert mfa.verify_code(key, "12345", None, now=59) is None and mfa.verify_code(key, "abcdef", None, now=59) is None


def test_secret_is_encrypted_at_rest_and_round_trips():
    s = mfa.new_secret()
    enc = mfa.encrypt_secret(s)
    assert s not in enc and mfa.decrypt_secret(enc) == s
    assert mfa.decrypt_secret("not-a-token") is None


def test_two_factor_login_flow(admin, clock):
    u, pw = _new_user(admin)
    s, r = _login(u["email"], pw)
    assert r.status_code == 200 and r.json()["user"]["totp_enabled"] is False
    secret = _enrol(s, clock)
    assert s.get("/api/v1/auth/me").json()["user"]["totp_enabled"] is True
    from app.db.models import User
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        stored = db.get(User, u["id"]).totp_secret_enc
    assert stored and secret not in stored                                     # encrypted, not plaintext

    # password alone no longer gives a session
    s2, r = _login(u["email"], pw)
    assert r.status_code == 200 and r.json() == {"mfa_required": True}
    assert "vantage_access" not in s2.c.cookies and s2.get("/api/v1/auth/me").status_code == 401
    # the code used for enrolment cannot be replayed
    assert s2.c.post("/api/v1/auth/login/mfa", json={"code": mfa.hotp(secret, clock["step"])}).status_code == 401
    clock["step"] += 1
    ok = s2.c.post("/api/v1/auth/login/mfa", json={"code": mfa.hotp(secret, clock["step"])})
    assert ok.status_code == 200 and s2.get("/api/v1/auth/me").status_code == 200
    # the pending-login token is single use
    clock["step"] += 1
    assert s2.c.post("/api/v1/auth/login/mfa", json={"code": mfa.hotp(secret, clock["step"])}).status_code == 401
    # no pending login at all
    assert Session().c.post("/api/v1/auth/login/mfa", json={"code": "123456"}).status_code == 401

    actions = [e["action"] for e in admin.get("/api/v1/admin/audit?limit=60").json() if e["resource"] == f"user:{u['id']}"]
    for a in ("mfa_enrolment_started", "mfa_enable_failed", "mfa_enabled", "login_password_ok_mfa_pending",
              "login_mfa_failed", "login_success"):
        assert a in actions, a
    assert not any(secret in str(e["detail"]) for e in admin.get("/api/v1/admin/audit?limit=60").json())


def test_wrong_codes_lock_the_account(admin, clock):
    u, pw = _new_user(admin)
    s, _ = _login(u["email"], pw)
    secret = _enrol(s, clock)
    clock["step"] += 1
    s2, r = _login(u["email"], pw)
    good = mfa.hotp(secret, clock["step"])
    bad = "000000" if good != "000000" else "111111"
    for _ in range(get_settings().max_failed_logins):
        assert s2.c.post("/api/v1/auth/login/mfa", json={"code": bad}).status_code == 401
    assert s2.c.post("/api/v1/auth/login/mfa", json={"code": good}).status_code == 401      # locked
    assert admin.post(f"/api/v1/admin/users/{u['id']}/unlock").status_code == 200


def test_disable_needs_password_and_code(admin, clock):
    u, pw = _new_user(admin)
    s, _ = _login(u["email"], pw)
    secret = _enrol(s, clock)
    clock["step"] += 1
    code = mfa.hotp(secret, clock["step"])
    assert s.post("/api/v1/auth/mfa/disable", json={"password": "Wrong-Passw0rd!", "code": code}).status_code == 401
    assert s.post("/api/v1/auth/mfa/disable", json={"password": pw, "code": code}).status_code == 200
    assert _login(u["email"], pw)[1].json()["user"]["totp_enabled"] is False


def test_admin_resets_lost_two_factor_but_never_their_own(admin, analyst, clock):
    u, pw = _new_user(admin)
    s, _ = _login(u["email"], pw)
    _enrol(s, clock)
    assert analyst.post(f"/api/v1/admin/users/{u['id']}/mfa/reset").status_code == 403
    me = admin.get("/api/v1/auth/me").json()["user"]["id"]
    assert admin.post(f"/api/v1/admin/users/{me}/mfa/reset").status_code == 409
    r = admin.post(f"/api/v1/admin/users/{u['id']}/mfa/reset")
    assert r.status_code == 200 and r.json()["totp_enabled"] is False
    assert _login(u["email"], pw)[1].json()["user"]["totp_enabled"] is False


def test_password_reset_link_is_single_use_hashed_and_signs_out(admin, analyst):
    u, pw = _new_user(admin)
    old, _ = _login(u["email"], pw)
    assert old.get("/api/v1/auth/me").status_code == 200
    assert analyst.post(f"/api/v1/admin/users/{u['id']}/password-reset").status_code == 403
    me = admin.get("/api/v1/auth/me").json()["user"]["id"]
    assert admin.post(f"/api/v1/admin/users/{me}/password-reset").status_code == 409

    first = admin.post(f"/api/v1/admin/users/{u['id']}/password-reset").json()["reset_path"].split("token=")[1]
    r = admin.post(f"/api/v1/admin/users/{u['id']}/password-reset")
    assert r.status_code == 200 and r.json()["reset_path"].startswith("/reset-password#token=")   # fragment: not logged
    token = r.json()["reset_path"].split("token=")[1]
    anon = Session()
    assert anon.c.post("/api/v1/auth/password-reset", json={"token": first, "new_password": NEW_PW}).status_code == 400
    assert anon.c.post("/api/v1/auth/password-reset", json={"token": token, "new_password": "weak"}).status_code == 422
    assert anon.c.post("/api/v1/auth/password-reset", json={"token": token, "new_password": NEW_PW}).status_code == 204
    assert anon.c.post("/api/v1/auth/password-reset", json={"token": token, "new_password": NEW_PW + "2"}).status_code == 400

    assert old.get("/api/v1/auth/me").status_code == 401                      # existing session signed out
    assert old.c.post("/api/v1/auth/refresh", headers=old._h()).status_code == 401
    assert _login(u["email"], pw)[1].status_code == 401
    assert _login(u["email"], NEW_PW)[1].status_code == 200

    from app.db.models import PasswordResetToken
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        rows = db.query(PasswordResetToken).filter_by(user_id=u["id"]).all()
    assert len(rows) == 2 and all(r.used_at for r in rows)
    assert all(token not in r.token_hash and first not in r.token_hash for r in rows)      # only hashes stored
    log = admin.get("/api/v1/admin/audit?limit=80").json()
    assert not any(token in str(e) or first in str(e) for e in log)
    assert {"password_reset_issued", "password_reset_completed", "password_reset_invalid"} <= {e["action"] for e in log}


def test_expired_reset_link_is_refused(admin):
    u, _ = _new_user(admin)
    token = admin.post(f"/api/v1/admin/users/{u['id']}/password-reset").json()["reset_path"].split("token=")[1]
    from app.db.models import PasswordResetToken
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        row = db.query(PasswordResetToken).filter_by(token_hash=mfa.hash_reset_token(token)).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert Session().c.post("/api/v1/auth/password-reset", json={"token": token, "new_password": NEW_PW}).status_code == 400


def test_change_own_password_signs_out_other_sessions(admin):
    u, pw = _new_user(admin)
    a, _ = _login(u["email"], pw)
    b, _ = _login(u["email"], pw)
    assert a.post("/api/v1/auth/password", json={"current_password": "Nope-Passw0rd!", "new_password": NEW_PW}).status_code == 401
    assert a.post("/api/v1/auth/password", json={"current_password": pw, "new_password": pw}).status_code == 422
    r = a.post("/api/v1/auth/password", json={"current_password": pw, "new_password": NEW_PW})
    assert r.status_code == 200
    assert a.get("/api/v1/auth/me").status_code == 200                        # this browser: fresh session
    assert b.get("/api/v1/auth/me").status_code == 401                        # other browser: signed out


def test_role_can_be_required_to_use_two_factor(admin, clock):
    s_ = get_settings()
    before = list(s_.mfa_required_roles)
    s_.mfa_required_roles = ["partner"]
    try:
        u, pw = _new_user(admin, role="partner")
        s, r = _login(u["email"], pw)
        assert r.status_code == 200 and r.json()["mfa_setup_required"] is True
        assert s.get("/api/v1/deals").status_code == 403                    # nothing but enrolment until set up
        assert s.get("/api/v1/auth/me").status_code == 200
        secret = _enrol(s, clock)
        assert s.get("/api/v1/auth/me").json()["mfa_setup_required"] is False
        assert s.get("/api/v1/deals").status_code == 200
        clock["step"] += 1
        r = s.post("/api/v1/auth/mfa/disable", json={"password": pw, "code": mfa.hotp(secret, clock["step"])})
        assert r.status_code == 409 and "mandatory" in r.text
    finally:
        s_.mfa_required_roles = before
