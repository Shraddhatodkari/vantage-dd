from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    audit,
    client_ip,
    deal_for,
    get_current_user,
    require,
    token_predates_password_change,
)
from app.api.schemas import (
    AuditOut,
    CodeIn,
    LoginIn,
    MemberIn,
    MfaChallenge,
    MfaDisableIn,
    PasswordChangeIn,
    PasswordResetIn,
    PublicConfig,
    SessionOut,
    UserCreate,
    UserOut,
)
from app.core import mfa
from app.core.config import get_settings
from app.core.permissions import Perm, perms_for
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import (
    create_access_token,
    create_mfa_pending_token,
    create_refresh_token,
    decode_token,
    hash_password,
    new_csrf_token,
    password_policy_errors,
    password_version,
    verify_password_constant_time,
)
from app.db.audit import verify_chain
from app.db.models import (
    AuditLog,
    Deal,
    DealMember,
    PasswordResetToken,
    RevokedToken,
    User,
)
from app.db.session import get_db

router = APIRouter(tags=["auth"])
login_limiter = SlidingWindowLimiter(get_settings().login_rate_limit_per_minute, 60)
GENERIC_LOGIN_ERROR = "Invalid email or password"
MFA_COOKIE = "vantage_mfa"
GENERIC_CODE_ERROR = "Invalid or expired code"


def _needs_mfa_setup(user: User) -> bool:
    return user.role in get_settings().mfa_required_roles and not user.totp_enabled


def _session_out(user: User, exp: datetime) -> SessionOut:
    return SessionOut(user=UserOut.model_validate(user), permissions=perms_for(user.role), access_expires_at=exp,
                      mfa_setup_required=_needs_mfa_setup(user))


def _set_session(resp: Response, user: User) -> datetime:
    s = get_settings()
    pwv = password_version(user.password_changed_at)
    access, _, a_exp = create_access_token(user.id, user.role, mfa_setup=_needs_mfa_setup(user), pwv=pwv)
    refresh, _, r_exp = create_refresh_token(user.id, user.role, pwv=pwv)
    common = {"httponly": True, "secure": s.cookie_secure, "samesite": "strict"}
    resp.set_cookie(ACCESS_COOKIE, access, max_age=s.access_token_minutes * 60, path="/", **common)
    resp.set_cookie(REFRESH_COOKIE, refresh, max_age=s.refresh_token_days * 86400, path=f"{s.api_prefix}/auth", **common)
    resp.set_cookie(CSRF_COOKIE, new_csrf_token(), max_age=s.refresh_token_days * 86400, path="/",
                    httponly=False, secure=s.cookie_secure, samesite="strict")
    return a_exp


def _clear_session(resp: Response) -> None:
    s = get_settings()
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie(REFRESH_COOKIE, path=f"{s.api_prefix}/auth")
    resp.delete_cookie(CSRF_COOKIE, path="/")
    resp.delete_cookie(MFA_COOKIE, path=f"{s.api_prefix}/auth/login")


def _revoke(db: Session, token: str | None, typ: str) -> None:
    if not token:
        return
    try:
        p = decode_token(token, typ)
    except ValueError:
        return
    if not db.get(RevokedToken, p["jti"]):
        db.add(RevokedToken(jti=p["jti"], expires_at=datetime.fromtimestamp(p["exp"], timezone.utc)))
        db.commit()


@router.get("/meta", response_model=PublicConfig)
def public_config(db: Session = Depends(get_db)):
    """Unauthenticated config for the login page. Never includes passwords."""
    s = get_settings()
    demo = s.demo_mode and s.env != "prod"
    accounts = [{"email": u.email, "role": u.role} for u in
                db.query(User).filter_by(is_demo_account=True, is_active=True).order_by(User.role)] if demo else []
    return PublicConfig(app_name=s.app_name, env=s.env, demo_mode=demo, demo_accounts=accounts, source_mode=s.source_mode)


@router.get("/ai/status")
def ai_status(_: User = Depends(get_current_user)):
    """Provider/execution mode shown in the UI next to every AI-dependent feature. No secrets are returned."""
    from app.agents.llm import provider_status
    return provider_status()


@router.post("/admin/ai/check")
def ai_check(request: Request, db: Session = Depends(get_db), user: User = Depends(require(Perm.USER_MANAGE))):
    """Administrator-triggered connectivity check (one tiny, disclosed API call when a provider is configured)."""
    from app.agents.llm import connectivity_check
    res = connectivity_check()
    audit(db, request, user, "ai_connectivity_check", "ai:provider", res, outcome="success" if res["ok"] else "failure")
    return res


@router.post("/auth/login", response_model=SessionOut | MfaChallenge)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    email = body.email.lower()
    if not login_limiter.allow(f"{client_ip(request)}:{email}"):
        audit(db, request, None, "login_rate_limited", f"email:{email}", outcome="denied")
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Wait a minute and try again.")
    user = db.query(User).filter(User.email == email).first()
    ok = verify_password_constant_time(body.password, user.hashed_password if user else None)
    if user and user.failed_logins >= s.max_failed_logins:
        audit(db, request, user, "login_blocked_locked", f"user:{user.id}", outcome="denied")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)  # same message: no account-state leak
    if not ok or not user or not user.is_active:
        if user:
            user.failed_logins += 1
            db.commit()
        audit(db, request, user, "login_failed", f"email:{email}", outcome="denied",
              detail={"failed_attempts": user.failed_logins if user else None})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)
    if user.totp_enabled:
        # password correct; no session until the authenticator code is verified (httpOnly, path-scoped cookie)
        tok, _, t_exp = create_mfa_pending_token(user.id, user.role)
        response.set_cookie(MFA_COOKIE, tok, max_age=s.mfa_login_minutes * 60, path=f"{s.api_prefix}/auth/login",
                            httponly=True, secure=s.cookie_secure, samesite="strict")
        audit(db, request, user, "login_password_ok_mfa_pending", f"user:{user.id}")
        return MfaChallenge()
    return _complete_login(db, request, response, user, mfa_used=False)


def _complete_login(db: Session, request: Request, response: Response, user: User, mfa_used: bool) -> SessionOut:
    user.failed_logins = 0
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    exp = _set_session(response, user)
    audit(db, request, user, "login_success", f"user:{user.id}", {"mfa": mfa_used})
    return _session_out(user, exp)


@router.post("/auth/login/mfa", response_model=SessionOut)
def login_mfa(body: CodeIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Second step: exchange the pending-login cookie plus a valid authenticator code for a session."""
    s = get_settings()
    token = request.cookies.get(MFA_COOKIE)
    try:
        p = decode_token(token or "", "mfa")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign-in expired; enter your password again") from None
    user = db.get(User, p["sub"])
    if not login_limiter.allow(f"{client_ip(request)}:mfa:{p['sub']}"):
        audit(db, request, user, "login_rate_limited", f"user:{p['sub']}", outcome="denied")
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Wait a minute and try again.")
    if db.get(RevokedToken, p["jti"]) or not user or not user.is_active or not user.totp_enabled:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign-in expired; enter your password again")
    if user.failed_logins >= s.max_failed_logins:
        audit(db, request, user, "login_blocked_locked", f"user:{user.id}", outcome="denied")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_CODE_ERROR)
    secret = mfa.decrypt_secret(user.totp_secret_enc or "")
    step = mfa.verify_code(secret, body.code, user.totp_last_step) if secret else None
    if step is None:
        user.failed_logins += 1
        db.commit()
        audit(db, request, user, "login_mfa_failed", f"user:{user.id}", outcome="denied",
              detail={"failed_attempts": user.failed_logins, "secret_readable": secret is not None})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_CODE_ERROR)
    user.totp_last_step = step
    _revoke(db, token, "mfa")                     # the pending-login token is single-use
    response.delete_cookie(MFA_COOKIE, path=f"{s.api_prefix}/auth/login")
    return _complete_login(db, request, response, user, mfa_used=True)


@router.post("/auth/refresh", response_model=SessionOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    try:
        p = decode_token(token or "", "refresh")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired; sign in again") from None
    if db.get(RevokedToken, p["jti"]):
        audit(db, request, None, "refresh_token_reuse", f"user:{p['sub']}", outcome="denied")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired; sign in again")
    user = db.get(User, p["sub"])
    if not user or not user.is_active or user.role != p.get("role") or token_predates_password_change(user, p):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired; sign in again")
    _revoke(db, token, "refresh")  # rotation: each refresh token is single-use
    exp = _set_session(response, user)
    return _session_out(user, exp)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    access = auth[7:] if auth.lower().startswith("bearer ") else request.cookies.get(ACCESS_COOKIE)
    _revoke(db, access, "access")
    _revoke(db, request.cookies.get(REFRESH_COOKIE), "refresh")
    try:
        sub = decode_token(access or "", "access")["sub"]
        user = db.get(User, sub)
    except ValueError:
        user = None
    audit(db, request, user, "logout", f"user:{user.id}" if user else "anonymous")
    _clear_session(response)
    response.status_code = 204
    return response


@router.get("/auth/session")
def current_session(request: Request, response: Response, db: Session = Depends(get_db)):
    """Session probe for page loads. Returns 200 {"authenticated": false} for anonymous users (no 401 noise).
    If only the access token expired, a valid refresh cookie is rotated server-side."""
    try:
        user = get_current_user(request, db)
        exp = datetime.fromtimestamp(request.state.token_payload["exp"], timezone.utc)
    except HTTPException:
        token = request.cookies.get(REFRESH_COOKIE)
        try:
            p = decode_token(token or "", "refresh")
        except ValueError:
            return {"authenticated": False}
        user = db.get(User, p["sub"])
        if (db.get(RevokedToken, p["jti"]) or not user or not user.is_active or user.role != p.get("role")
                or token_predates_password_change(user, p)):
            return {"authenticated": False}
        _revoke(db, token, "refresh")
        exp = _set_session(response, user)
    return {"authenticated": True, **_session_out(user, exp).model_dump(mode="json")}


@router.get("/auth/me", response_model=SessionOut)
def me(request: Request, user: User = Depends(get_current_user)):
    exp = datetime.fromtimestamp(request.state.token_payload["exp"], timezone.utc)
    return _session_out(user, exp)


# ---------------------------------------------------------------- two-factor authentication (self-service)
@router.post("/auth/mfa/setup")
def mfa_setup(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Start enrolment: a new secret is stored encrypted but NOT active until a code from the app is confirmed.
    The secret is shown once, to the signed-in user only, so it can be added to an authenticator app."""
    if user.totp_enabled:
        raise HTTPException(409, "Two-factor authentication is already enabled; disable it first to re-enrol")
    secret = mfa.new_secret()
    user.totp_secret_enc, user.totp_last_step = mfa.encrypt_secret(secret), None
    db.commit()
    uri = mfa.provisioning_uri(secret, user.email)
    audit(db, request, user, "mfa_enrolment_started", f"user:{user.id}")
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": mfa.qr_svg(uri)}


@router.post("/auth/mfa/enable", response_model=SessionOut)
def mfa_enable(body: CodeIn, request: Request, response: Response, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if user.totp_enabled:
        raise HTTPException(409, "Two-factor authentication is already enabled")
    secret = mfa.decrypt_secret(user.totp_secret_enc or "")
    step = mfa.verify_code(secret, body.code, None) if secret else None
    if step is None:
        audit(db, request, user, "mfa_enable_failed", f"user:{user.id}", outcome="denied")
        raise HTTPException(422, "That code does not match. Check the time on your phone and try the next code.")
    user.totp_enabled, user.totp_last_step = True, step
    db.commit()
    audit(db, request, user, "mfa_enabled", f"user:{user.id}")
    exp = _set_session(response, user)          # a new session without the 'set up 2FA first' restriction
    return _session_out(user, exp)


@router.post("/auth/mfa/disable", response_model=UserOut)
def mfa_disable(body: MfaDisableIn, request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    if not user.totp_enabled:
        raise HTTPException(409, "Two-factor authentication is not enabled")
    if user.role in get_settings().mfa_required_roles:
        raise HTTPException(409, f"Two-factor authentication is mandatory for the {user.role} role")
    secret = mfa.decrypt_secret(user.totp_secret_enc or "")
    step = mfa.verify_code(secret, body.code, user.totp_last_step) if secret else None
    if not verify_password_constant_time(body.password, user.hashed_password) or step is None:
        audit(db, request, user, "mfa_disable_failed", f"user:{user.id}", outcome="denied")
        raise HTTPException(401, "Password or code is incorrect")
    user.totp_enabled, user.totp_secret_enc, user.totp_last_step = False, None, None
    db.commit()
    audit(db, request, user, "mfa_disabled", f"user:{user.id}")
    return user


# ---------------------------------------------------------------- passwords
def _set_password(user: User, new_password: str) -> None:
    if errs := password_policy_errors(new_password):
        raise HTTPException(422, "Password must contain " + ", ".join(errs))
    if verify_password_constant_time(new_password, user.hashed_password):
        raise HTTPException(422, "The new password must differ from the current one")
    user.hashed_password = hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc)   # every older session stops working
    user.failed_logins = 0


@router.post("/auth/password", response_model=SessionOut)
def change_password(body: PasswordChangeIn, request: Request, response: Response, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Change your own password. Signs out every other session; this browser gets a fresh one."""
    ok = verify_password_constant_time(body.current_password, user.hashed_password)
    if ok and user.totp_enabled:
        secret = mfa.decrypt_secret(user.totp_secret_enc or "")
        step = mfa.verify_code(secret, body.code or "", user.totp_last_step) if secret else None
        ok = step is not None
        if ok:
            user.totp_last_step = step
    if not ok:
        audit(db, request, user, "password_change_failed", f"user:{user.id}", outcome="denied")
        raise HTTPException(401, "Current password or code is incorrect")
    _set_password(user, body.new_password)
    db.commit()
    _revoke(db, request.cookies.get(REFRESH_COOKIE), "refresh")
    audit(db, request, user, "password_changed", f"user:{user.id}")
    exp = _set_session(response, user)
    return _session_out(user, exp)


@router.post("/auth/password-reset", status_code=204)
def complete_password_reset(body: PasswordResetIn, request: Request, response: Response,
                            db: Session = Depends(get_db)):
    """Redeem an administrator-issued reset link. Single use, time-limited; 2FA (if enabled) stays enabled."""
    if not login_limiter.allow(f"{client_ip(request)}:password-reset"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Wait a minute and try again.")
    row = db.query(PasswordResetToken).filter_by(token_hash=mfa.hash_reset_token(body.token)).first()
    now = datetime.now(timezone.utc)
    exp = row.expires_at.replace(tzinfo=row.expires_at.tzinfo or timezone.utc) if row else None
    user = db.get(User, row.user_id) if row else None
    if not row or row.used_at is not None or exp < now or not user or not user.is_active:
        audit(db, request, user, "password_reset_invalid", f"user:{user.id}" if user else "anonymous", outcome="denied",
              detail={"reason": "unknown" if not row else "used" if row.used_at else "expired" if exp < now else "inactive"})
        raise HTTPException(400, "This reset link is invalid, already used or expired. Ask an administrator for a new one.")
    _set_password(user, body.new_password)
    row.used_at = now
    db.commit()
    audit(db, request, user, "password_reset_completed", f"user:{user.id}", {"issued_by": row.created_by})
    _clear_session(response)
    response.status_code = 204
    return response


# ---------------------------------------------------------------- administration
@router.get("/admin/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require(Perm.USER_MANAGE))):
    return db.query(User).order_by(User.created_at).all()


@router.post("/admin/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, request: Request, db: Session = Depends(get_db),
                admin: User = Depends(require(Perm.USER_MANAGE))):
    if errs := password_policy_errors(body.password):
        raise HTTPException(422, "Password must contain " + ", ".join(errs))
    if db.query(User).filter_by(email=body.email.lower()).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    u = User(email=body.email.lower(), full_name=body.full_name, role=body.role, hashed_password=hash_password(body.password))
    db.add(u)
    db.commit()
    audit(db, request, admin, "user_created", f"user:{u.id}", {"email": u.email, "role": u.role})
    return u


@router.post("/admin/users/{user_id}/unlock", response_model=UserOut)
def unlock_user(user_id: str, request: Request, db: Session = Depends(get_db),
                admin: User = Depends(require(Perm.USER_MANAGE))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    before = u.failed_logins
    u.failed_logins = 0
    db.commit()
    audit(db, request, admin, "user_unlocked", f"user:{u.id}", {"failed_logins_before": before})
    return u


@router.post("/admin/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: str, request: Request, db: Session = Depends(get_db),
                    admin: User = Depends(require(Perm.USER_MANAGE))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(409, "Administrators cannot deactivate themselves")
    u.is_active = False
    db.commit()
    audit(db, request, admin, "user_deactivated", f"user:{u.id}", {"email": u.email})
    return u


@router.post("/admin/users/{user_id}/password-reset")
def issue_password_reset(user_id: str, request: Request, db: Session = Depends(get_db),
                         admin: User = Depends(require(Perm.USER_MANAGE))):
    """Issue a single-use reset link for another user. The token is returned once (to give to the user through a
    trusted channel) and stored only as a SHA-256 hash; earlier unused links for that user are cancelled."""
    u = db.get(User, user_id)
    if not u or not u.is_active:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(409, "Change your own password from Account security; another administrator must reset it")
    now = datetime.now(timezone.utc)
    for old in db.query(PasswordResetToken).filter_by(user_id=u.id, used_at=None):
        old.used_at = now                            # cancelled
    token, digest = mfa.new_reset_token()
    minutes = get_settings().password_reset_minutes
    row = PasswordResetToken(user_id=u.id, token_hash=digest, created_by=admin.id, expires_at=now + timedelta(minutes=minutes))
    db.add(row)
    db.commit()
    audit(db, request, admin, "password_reset_issued", f"user:{u.id}", {"email": u.email, "expires_minutes": minutes})
    return {"reset_path": f"/reset-password#token={token}", "expires_at": row.expires_at, "expires_minutes": minutes}


@router.post("/admin/users/{user_id}/mfa/reset", response_model=UserOut)
def reset_user_mfa(user_id: str, request: Request, db: Session = Depends(get_db),
                   admin: User = Depends(require(Perm.USER_MANAGE))):
    """For a user who lost their phone: removes their 2FA so they can enrol again. Never for yourself."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(409, "Another administrator must reset your two-factor authentication")
    was = u.totp_enabled
    u.totp_enabled, u.totp_secret_enc, u.totp_last_step = False, None, None
    db.commit()
    audit(db, request, admin, "mfa_reset_by_admin", f"user:{u.id}", {"email": u.email, "was_enabled": was})
    return u


@router.post("/deals/{deal_id}/members", status_code=201)
def add_member(deal_id: str, body: MemberIn, request: Request, db: Session = Depends(get_db),
               user: User = Depends(require(Perm.DEAL_MANAGE_MEMBERS))):
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(404, "Deal not found")
    if user.role != "admin":  # partners may only staff deals they are on
        deal_for(db, deal_id, user, Perm.DEAL_READ, request)
    target = db.get(User, body.user_id)
    if not target or not target.is_active:
        raise HTTPException(404, "User not found")
    if not db.query(DealMember).filter_by(deal_id=deal_id, user_id=target.id).first():
        db.add(DealMember(deal_id=deal_id, user_id=target.id, added_by=user.id))
        db.commit()
    audit(db, request, user, "deal_member_added", f"deal:{deal_id}", {"member": target.email})
    return {"deal_id": deal_id, "user_id": target.id}


@router.get("/admin/audit", response_model=list[AuditOut])
def audit_log(limit: int = 300, db: Session = Depends(get_db), _: User = Depends(require(Perm.AUDIT_READ))):
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 2000)).all()


@router.get("/admin/audit/verify")
def audit_verify(request: Request, db: Session = Depends(get_db), admin: User = Depends(require(Perm.AUDIT_READ))):
    res = verify_chain(db)
    audit(db, request, admin, "audit_chain_verified", "audit_log", res, outcome="success" if res["valid"] else "failure")
    return res
