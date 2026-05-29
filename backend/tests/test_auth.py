"""
Tests for /api/v1/auth/* endpoints:
  POST /register
  POST /login
  GET  /me
  PATCH /me
  POST /change-password
  POST /forgot-password
  POST /reset-password
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password, create_access_token, generate_reset_token, hash_reset_token
from app.models.user import User


# ── Register ──────────────────────────────────────────────────────────────────

class TestRegister:
    URL = "/api/v1/auth/register"

    def test_register_success(self, client):
        r = client.post(self.URL, json={
            "email": "new@example.com",
            "full_name": "New User",
            "password": "StrongPass1!",
            "role": "user",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["user"]["email"] == "new@example.com"
        assert "access_token" in body
        assert body["expires_in"] > 0

    def test_register_duplicate_email(self, client, test_user):
        r = client.post(self.URL, json={
            "email": test_user.email,
            "full_name": "Dup",
            "password": "StrongPass1!",
            "role": "user",
        })
        assert r.status_code == 409
        assert "already exists" in r.json()["detail"].lower()

    def test_register_missing_fields(self, client):
        r = client.post(self.URL, json={"email": "x@x.com"})
        assert r.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    URL = "/api/v1/auth/login"

    def test_login_success(self, client, test_user):
        r = client.post(self.URL, json={
            "email": test_user.email,
            "password": "Test@Password1",
        })
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["expires_in"] > 0

    def test_login_wrong_password(self, client, test_user):
        r = client.post(self.URL, json={
            "email": test_user.email,
            "password": "WrongPassword!",
        })
        assert r.status_code == 401

    def test_login_unknown_email(self, client):
        r = client.post(self.URL, json={
            "email": "nobody@nowhere.com",
            "password": "Whatever1!",
        })
        assert r.status_code == 401

    def test_login_inactive_user(self, client, db, test_user):
        test_user.is_active = False
        db.commit()
        r = client.post(self.URL, json={
            "email": test_user.email,
            "password": "Test@Password1",
        })
        assert r.status_code == 403


# ── GET /me ───────────────────────────────────────────────────────────────────

class TestGetMe:
    URL = "/api/v1/auth/me"

    def test_get_me_authenticated(self, client, auth_headers, test_user):
        r = client.get(self.URL, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["email"] == test_user.email

    def test_get_me_no_token(self, client):
        r = client.get(self.URL)
        assert r.status_code == 401

    def test_get_me_invalid_token(self, client):
        r = client.get(self.URL, headers={"Authorization": "Bearer notavalidtoken"})
        assert r.status_code == 401


# ── PATCH /me ─────────────────────────────────────────────────────────────────

class TestUpdateMe:
    URL = "/api/v1/auth/me"

    def test_update_name(self, client, auth_headers):
        r = client.patch(self.URL, json={"full_name": "Updated Name"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["full_name"] == "Updated Name"

    def test_update_currency_uppercased(self, client, auth_headers):
        r = client.patch(self.URL, json={"preferred_currency": "eur"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["preferred_currency"] == "EUR"

    def test_update_requires_auth(self, client):
        r = client.patch(self.URL, json={"full_name": "No Auth"})
        assert r.status_code == 401


# ── POST /change-password ─────────────────────────────────────────────────────

class TestChangePassword:
    URL = "/api/v1/auth/change-password"

    def test_change_password_success(self, client, auth_headers, db, test_user):
        r = client.post(self.URL, json={
            "current_password": "Test@Password1",
            "new_password": "NewSecure2!",
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["message"] == "Password updated successfully"

    def test_change_password_wrong_current(self, client, auth_headers):
        r = client.post(self.URL, json={
            "current_password": "WrongOldPass!",
            "new_password": "NewSecure2!",
        }, headers=auth_headers)
        assert r.status_code == 400

    def test_change_password_requires_auth(self, client):
        r = client.post(self.URL, json={
            "current_password": "Test@Password1",
            "new_password": "NewSecure2!",
        })
        assert r.status_code == 401


# ── POST /forgot-password ─────────────────────────────────────────────────────

class TestForgotPassword:
    URL = "/api/v1/auth/forgot-password"

    def test_forgot_password_known_email(self, client, test_user, db):
        """Always returns 200 regardless of whether email exists (anti-enumeration)."""
        r = client.post(self.URL, json={"email": test_user.email})
        assert r.status_code == 200
        assert "reset link" in r.json()["message"].lower()

    def test_forgot_password_unknown_email(self, client):
        r = client.post(self.URL, json={"email": "nobody@nowhere.com"})
        assert r.status_code == 200  # same response to prevent enumeration


# ── POST /reset-password ──────────────────────────────────────────────────────

class TestResetPassword:
    URL = "/api/v1/auth/reset-password"

    def test_reset_password_success(self, client, db, test_user):
        raw, hashed = generate_reset_token()
        test_user.reset_token = hashed
        test_user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()

        r = client.post(self.URL, json={
            "token": raw,
            "new_password": "BrandNew3!",
        })
        assert r.status_code == 200
        assert "reset successfully" in r.json()["message"].lower()

    def test_reset_password_invalid_token(self, client):
        r = client.post(self.URL, json={
            "token": "completely-invalid-token",
            "new_password": "BrandNew3!",
        })
        assert r.status_code == 400

    def test_reset_password_expired_token(self, client, db, test_user):
        raw, hashed = generate_reset_token()
        test_user.reset_token = hashed
        test_user.reset_token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

        r = client.post(self.URL, json={
            "token": raw,
            "new_password": "BrandNew3!",
        })
        assert r.status_code == 400
        assert "expired" in r.json()["detail"].lower()
