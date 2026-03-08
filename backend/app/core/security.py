"""Core security utilities — password hashing and JWT token management."""

import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT tokens ────────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, int]:
    """
    Create a signed JWT access token.

    Returns:
        (token_string, expires_in_seconds)
    """
    expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    expires_in = int((expire - datetime.now(timezone.utc)).total_seconds())
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT access token.

    Raises:
        jwt.ExpiredSignatureError  — token has expired
        jwt.InvalidTokenError      — token is invalid / tampered
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )


# ── Password reset tokens ─────────────────────────────────────────────────────

def generate_reset_token() -> tuple[str, str]:
    """
    Generate a password-reset token pair.

    Returns:
        (raw_token, hashed_token)
        - raw_token: sent to the user via email (URL-safe, 32 bytes)
        - hashed_token: stored in users.reset_token
    """
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_reset_token(raw: str) -> str:
    """Hash a raw reset token for comparison against the stored hash."""
    return hashlib.sha256(raw.encode()).hexdigest()
