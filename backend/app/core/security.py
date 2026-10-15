"""Password hashing (bcrypt), password policy and JWT issuance/validation.

Tokens are delivered to the browser in httpOnly cookies (not readable by JavaScript) and may also be
sent as a Bearer header by API clients. Every token carries a `jti`; logout and refresh rotation
revoke the jti server-side, so a stolen token stops working once revoked.
"""
from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import bcrypt
import jwt
from jwt import PyJWTError as JWTError

from app.core.config import get_settings


class Role(str, Enum):
    ANALYST = "analyst"
    PARTNER = "partner"
    ADMIN = "admin"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


# A real hash is always checked (even for unknown users) so response time does not reveal
# whether an account exists.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def verify_password_constant_time(password: str, hashed: str | None) -> bool:
    if hashed is None:
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, hashed)


def password_policy_errors(password: str) -> list[str]:
    s = get_settings()
    errs = []
    if len(password) < s.min_password_length:
        errs.append(f"at least {s.min_password_length} characters")
    if not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password):
        errs.append("upper- and lower-case letters")
    if not re.search(r"\d", password):
        errs.append("a digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        errs.append("a symbol")
    return errs


def _create_token(subject: str, role: str, token_type: str, expires: timedelta,
                  extra: dict | None = None) -> tuple[str, str, datetime]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + expires
    jti = uuid.uuid4().hex
    payload = {"sub": subject, "role": role, "type": token_type, "iat": int(now.timestamp()),
               "exp": int(exp.timestamp()), "jti": jti, **(extra or {})}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), jti, exp


def create_access_token(subject: str, role: str, mfa_setup: bool = False, pwv: int = 0) -> tuple[str, str, datetime]:
    extra = {"pwv": pwv, **({"mfa_setup": True} if mfa_setup else {})}
    return _create_token(subject, role, "access", timedelta(minutes=get_settings().access_token_minutes), extra)


def create_mfa_pending_token(subject: str, role: str) -> tuple[str, str, datetime]:
    """Short-lived proof that the password step succeeded; only exchangeable for a session with a valid code."""
    return _create_token(subject, role, "mfa", timedelta(minutes=get_settings().mfa_login_minutes))


def create_refresh_token(subject: str, role: str, pwv: int = 0) -> tuple[str, str, datetime]:
    return _create_token(subject, role, "refresh", timedelta(days=get_settings().refresh_token_days), {"pwv": pwv})


def decode_token(token: str, expected_type: str = "access") -> dict:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
    if payload.get("type") != expected_type:
        raise ValueError("wrong token type")
    return payload


def password_version(changed_at: datetime | None) -> int:
    """Stamp carried in every session token; a password change or reset changes it, invalidating older sessions
    exactly (microseconds), even ones issued in the same second."""
    if changed_at is None:
        return 0
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    return int(changed_at.timestamp() * 1_000_000)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
