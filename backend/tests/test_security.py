"""
Pure unit tests for app.core.security — no DB, no HTTP.

Covers:
  hash_password / verify_password
  create_access_token / decode_access_token
  generate_reset_token / hash_reset_token
"""

from datetime import timedelta

import jwt
import pytest

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_reset_token,
    hash_reset_token,
)


# ── Password hashing ──────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_returns_string(self):
        h = hash_password("secret")
        assert isinstance(h, str)
        assert len(h) > 0

    def test_hash_is_not_plain_text(self):
        h = hash_password("secret")
        assert h != "secret"

    def test_hash_starts_with_bcrypt_prefix(self):
        h = hash_password("secret")
        assert h.startswith("$2b$") or h.startswith("$2a$")

    def test_verify_correct_password(self):
        h = hash_password("correcthorsebatterystaple")
        assert verify_password("correcthorsebatterystaple", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("correcthorsebatterystaple")
        assert verify_password("wrongpassword", h) is False

    def test_two_hashes_of_same_password_differ(self):
        """bcrypt uses random salt — hashes must not be equal."""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2

    def test_both_hashes_verify_correctly(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert verify_password("same", h1) is True
        assert verify_password("same", h2) is True

    def test_unicode_password(self):
        pw = "كلمة_سر_قوية_1!"
        h = hash_password(pw)
        assert verify_password(pw, h) is True


# ── JWT tokens ────────────────────────────────────────────────────────────────

class TestJwt:
    def test_create_returns_token_and_expiry(self):
        token, expires_in = create_access_token("user-123")
        assert isinstance(token, str)
        assert len(token) > 0
        assert expires_in > 0

    def test_decode_valid_token(self):
        token, _ = create_access_token("user-123")
        payload = decode_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_extra_claims_present_in_token(self):
        token, _ = create_access_token(
            "user-456",
            extra_claims={"role": "admin", "email": "admin@test.com"},
        )
        payload = decode_access_token(token)
        assert payload["role"] == "admin"
        assert payload["email"] == "admin@test.com"

    def test_expired_token_raises(self):
        token, _ = create_access_token(
            "user-789",
            expires_delta=timedelta(seconds=-1),  # already expired
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_tampered_token_raises(self):
        token, _ = create_access_token("user-000")
        tampered = token[:-4] + "xxxx"
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(tampered)

    def test_garbage_token_raises(self):
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token("not.a.token")

    def test_expires_in_matches_configured_minutes(self):
        """expires_in should be close to ACCESS_TOKEN_EXPIRE_MINUTES * 60."""
        from app.core.config import settings
        _, expires_in = create_access_token("user-999")
        expected = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        # Allow a few seconds of clock drift
        assert abs(expires_in - expected) < 5

    def test_custom_expiry_respected(self):
        _, expires_in = create_access_token(
            "user-custom",
            expires_delta=timedelta(hours=2),
        )
        assert abs(expires_in - 7200) < 5


# ── Reset tokens ──────────────────────────────────────────────────────────────

class TestResetTokens:
    def test_generate_returns_two_strings(self):
        raw, hashed = generate_reset_token()
        assert isinstance(raw, str)
        assert isinstance(hashed, str)

    def test_raw_and_hashed_differ(self):
        raw, hashed = generate_reset_token()
        assert raw != hashed

    def test_hash_reset_token_matches_generated(self):
        raw, hashed = generate_reset_token()
        assert hash_reset_token(raw) == hashed

    def test_different_raws_produce_different_hashes(self):
        raw1, h1 = generate_reset_token()
        raw2, h2 = generate_reset_token()
        assert h1 != h2

    def test_raw_is_url_safe(self):
        """token_urlsafe output must not contain URL-unsafe chars."""
        raw, _ = generate_reset_token()
        import re
        assert re.fullmatch(r"[A-Za-z0-9_\-]+", raw), f"Unsafe chars in: {raw}"

    def test_hash_is_hex_sha256(self):
        """SHA-256 hex digest is always 64 hex chars."""
        _, hashed = generate_reset_token()
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)
