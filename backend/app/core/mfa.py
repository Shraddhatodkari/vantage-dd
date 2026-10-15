"""Two-factor authentication with authenticator-app codes (TOTP, RFC 6238: HMAC-SHA1, 30-second steps, 6 digits),
plus single-use password-reset tokens.

* The TOTP secret is encrypted at rest (Fernet, AES-128-CBC + HMAC-SHA256). The key comes from
  VANTAGE_MFA_ENCRYPTION_KEY or, when unset, is derived from the JWT secret with HKDF (separate purpose label).
  Rotating that secret therefore requires users to re-enrol (an administrator can reset 2FA).
* A code is accepted for the current step +/- 1 (clock drift) and never twice: the last accepted step is stored,
  so a code observed in transit cannot be replayed.
* Password-reset tokens are random 256-bit values shown once; only their SHA-256 hash is stored.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

STEP_SECONDS, DIGITS, WINDOW = 30, 6, 1


def new_secret() -> str:
    """160-bit secret, base32 without padding (what authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _b32(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def hotp(secret: str, counter: int, digits: int = DIGITS) -> str:
    """RFC 4226 HOTP value for a counter."""
    mac = hmac.new(_b32(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    o = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** digits
    return str(code).zfill(digits)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def verify_code(secret: str, code: str, last_step: int | None, now: float | None = None) -> int | None:
    """Return the matched time step (to store as the new last_step) or None. Constant-time comparison; steps at or
    before last_step are refused (replay)."""
    code = (code or "").strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    step, match = current_step(now), None
    for s in range(step - WINDOW, step + WINDOW + 1):
        if hmac.compare_digest(hotp(secret, s), code) and (last_step is None or s > last_step):
            match = s           # keep looping: same work for every input
    return match


def provisioning_uri(secret: str, account: str) -> str:
    issuer = get_settings().mfa_issuer
    q = urlencode({"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": DIGITS, "period": STEP_SECONDS})
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?{q}"


def qr_svg(uri: str) -> str:
    """Inline SVG QR code of the provisioning URI (generated locally; the secret never leaves the server)."""
    import io

    import segno
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=4, border=2, xmldecl=False, svgns=True)
    return buf.getvalue().decode("utf-8")


def _fernet() -> Fernet:
    s = get_settings()
    if s.mfa_encryption_key:
        return Fernet(s.mfa_encryption_key.encode())
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"vantage-dd", info=b"totp-secret-encryption").derive(
        s.jwt_secret.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def new_reset_token() -> tuple[str, str]:
    """(token shown once to the administrator, SHA-256 hash stored in the database)."""
    t = secrets.token_urlsafe(32)
    return t, hash_reset_token(t)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
