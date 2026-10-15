"""Authentication (cookie or Bearer), CSRF, permission and deal-membership enforcement.

Browser sessions use httpOnly cookies + a double-submit CSRF token (header X-CSRF-Token must equal the
vantage_csrf cookie on state-changing requests). API clients may send `Authorization: Bearer`, which
is not sent automatically by browsers and therefore needs no CSRF token.
"""
from __future__ import annotations

import hmac
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.permissions import Perm, has_perm
from app.core.security import decode_token, password_version
from app.db.audit import write_audit
from app.db.models import Deal, DealMember, RevokedToken, User
from app.db.session import get_db

ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE = "vantage_access", "vantage_refresh", "vantage_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def client_ip(request: Request | None) -> str | None:
    return request.client.host if request and request.client else None


def _token_from(request: Request) -> tuple[str | None, bool]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip(), False
    return request.cookies.get(ACCESS_COOKIE), True


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token, via_cookie = _token_from(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(token, "access")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session") from None
    if db.get(RevokedToken, payload["jti"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session has been signed out")
    if via_cookie and request.method not in SAFE_METHODS:
        sent, cookie = request.headers.get("x-csrf-token", ""), request.cookies.get(CSRF_COOKIE, "")
        if not sent or not cookie or not hmac.compare_digest(sent, cookie):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    if user.role != payload.get("role"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Role changed; sign in again")
    if token_predates_password_change(user, payload):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password changed; sign in again")
    if payload.get("mfa_setup") and request.url.path.split("/api/v1", 1)[-1] not in MFA_SETUP_PATHS:
        # role requires 2FA and the user has not enrolled yet: only enrolment and sign-out are allowed
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Two-factor authentication must be set up before continuing")
    request.state.token_payload = payload
    return user


MFA_SETUP_PATHS = {"/auth/me", "/auth/session", "/auth/logout", "/auth/mfa/setup", "/auth/mfa/enable", "/auth/password"}


def token_predates_password_change(user: User, payload: dict) -> bool:
    """Sessions issued before the last password change/reset carry an older password-version stamp (exact match,
    so even a session created in the same second as the change is invalidated)."""
    return int(payload.get("pwv", 0)) != password_version(user.password_changed_at)


def require(perm: Perm) -> Callable[..., User]:
    def checker(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not has_perm(user.role, perm):
            write_audit(db, user_id=user.id, user_email=user.email, action="permission_denied",
                        resource=request.url.path, outcome="denied", detail={"permission": perm.value},
                        ip=client_ip(request))
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Your role does not grant '{perm.value}'")
        return user
    return checker


def is_member(db: Session, deal_id: str, user_id: str) -> bool:
    return db.query(DealMember).filter_by(deal_id=deal_id, user_id=user_id).first() is not None


def deal_for(db: Session, deal_id: str, user: User, perm: Perm, request: Request | None = None) -> Deal:
    """Fetch a deal, enforcing role permission AND deal membership. Non-members get 404 (no existence leak)."""
    deal = db.get(Deal, deal_id)
    if not deal or not has_perm(user.role, perm) or not is_member(db, deal_id, user.id):
        if deal:
            write_audit(db, user_id=user.id, user_email=user.email, action="deal_access_denied",
                        resource=f"deal:{deal_id}", outcome="denied", detail={"permission": perm.value},
                        ip=client_ip(request))
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deal not found")
    return deal


def audit(db: Session, request: Request | None, user: User | None, action: str, resource: str,
          detail: dict | None = None, outcome: str = "success") -> None:
    write_audit(db, user_id=user.id if user else None, user_email=user.email if user else None, action=action,
                resource=resource, outcome=outcome, detail=detail, ip=client_ip(request))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
