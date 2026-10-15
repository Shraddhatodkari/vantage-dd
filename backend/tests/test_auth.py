"""Authentication & session security (API level)."""
import logging

from app.api.routes_auth import login_limiter
from app.core.config import ConfigError, Settings, validate_settings

from .conftest import PASSWORD, Session


def test_login_sets_httponly_cookies_and_returns_no_token(app_started):
    s = Session()
    r = s.c.post("/api/v1/auth/login", json={"email": "analyst@vantage.dev", "password": PASSWORD})
    assert r.status_code == 200
    body = r.text
    assert "access_token" not in body and "refresh" not in body.lower()
    cookies = r.headers.get_list("set-cookie")
    access = next(c for c in cookies if c.startswith("vantage_access="))
    assert "HttpOnly" in access and "SameSite=strict" in access.replace("Strict", "strict")
    assert any(c.startswith("vantage_csrf=") and "HttpOnly" not in c for c in cookies)


def test_invalid_login_is_generic_for_unknown_and_wrong_password(app_started):
    s = Session()
    a = s.c.post("/api/v1/auth/login", json={"email": "nobody@vantage.dev", "password": "wrong-password-1"})
    b = s.c.post("/api/v1/auth/login", json={"email": "admin@vantage.dev", "password": "wrong-password-1"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
    login_limiter.reset()


def test_validation_errors_never_echo_the_password(app_started):
    r = Session().c.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "S3cret-Value!"})
    assert r.status_code == 422 and "S3cret-Value!" not in r.text


def test_password_never_logged(app_started, caplog):
    caplog.set_level(logging.DEBUG)
    Session().c.post("/api/v1/auth/login", json={"email": "analyst@vantage.dev", "password": "Wrong-Pass-123!"})
    assert "Wrong-Pass-123!" not in caplog.text and PASSWORD not in caplog.text
    login_limiter.reset()


def test_csrf_required_for_cookie_authenticated_writes(analyst):
    r = analyst.c.post("/api/v1/deals", json={"name": "No CSRF deal", "target_company": "X", "deal_type": "credit",
                                              "sector": "Test"})
    assert r.status_code == 403 and "CSRF" in r.text


def test_logout_revokes_the_session(app_started):
    s = Session("analyst@vantage.dev")
    old_access = s.c.cookies.get("vantage_access")
    assert s.post("/api/v1/auth/logout").status_code == 204
    r = Session().c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"})
    assert r.status_code == 401 and "signed out" in r.text


def test_refresh_rotation_rejects_reuse(app_started):
    s = Session("partner@vantage.dev")
    old_refresh = s.c.cookies.get("vantage_refresh")
    assert s.post("/api/v1/auth/refresh").status_code == 200
    s2 = Session()
    s2.c.cookies.set("vantage_refresh", old_refresh, path="/api/v1/auth")
    assert s2.c.post("/api/v1/auth/refresh").status_code == 401


def test_account_lockout_after_repeated_failures(admin):
    admin.post("/api/v1/admin/users", json={"email": "lock@vantage.dev", "full_name": "Lock Test",
                                            "password": "Lock-Test#Pass2026", "role": "analyst"})
    for _ in range(5):
        Session().c.post("/api/v1/auth/login", json={"email": "lock@vantage.dev", "password": "wrong-password-9"})
    login_limiter.reset()
    r = Session().c.post("/api/v1/auth/login", json={"email": "lock@vantage.dev", "password": "Lock-Test#Pass2026"})
    assert r.status_code == 401  # locked, with the same generic message


def test_password_policy_enforced_on_user_creation(admin):
    r = admin.post("/api/v1/admin/users", json={"email": "weak@vantage.dev", "full_name": "Weak", "password": "alllowercase1",
                                                "role": "analyst"})
    assert r.status_code == 422


def test_public_config_lists_demo_accounts_without_passwords(app_started):
    j = Session().c.get("/api/v1/meta").json()
    assert j["demo_mode"] is True and {a["role"] for a in j["demo_accounts"]} == {"admin", "analyst", "partner"}
    assert PASSWORD not in str(j) and "password" not in str(j).lower()


def test_production_config_refuses_demo_mode_and_weak_secrets():
    import pytest
    with pytest.raises(ConfigError) as e:
        validate_settings(Settings(env="prod", demo_mode=True, seed_password="Aa1!aaaaaaaaaa", jwt_secret="short"))
    msg = str(e.value)
    assert "DEMO_MODE" in msg and "JWT_SECRET" in msg and "COOKIE_SECURE" in msg
    ok = Settings(env="prod", demo_mode=False, jwt_secret="x" * 40, cookie_secure=True,
                  cors_origins=["https://dd.example.com"])
    assert validate_settings(ok) == []


def test_security_headers_present(app_started):
    r = Session().c.get("/healthz")
    assert r.headers["x-frame-options"] == "DENY" and "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_session_probe_is_quiet_for_anonymous_and_refreshes_expired_access(app_started):
    anon = Session().c.get("/api/v1/auth/session")
    assert anon.status_code == 200 and anon.json() == {"authenticated": False}
    s = Session("analyst@vantage.dev")
    s.c.cookies.delete("vantage_access")  # simulate access-token expiry
    r = s.c.get("/api/v1/auth/session")
    assert r.status_code == 200 and r.json()["authenticated"] and r.json()["user"]["email"] == "analyst@vantage.dev"
    assert "vantage_access=" in " ".join(r.headers.get_list("set-cookie"))
