"""Pydantic schemas for Auth endpoints — request bodies and response shapes."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
import uuid


# ── Request bodies ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    # Users can only self-register as "user" or "analyst".
    # Admin accounts are created separately via the secret admin panel.
    role: str = Field(default="user", pattern="^(user|analyst)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminLoginRequest(BaseModel):
    """Used exclusively by the secret ESC-triggered admin login panel."""
    email: EmailStr
    password: str
    # Anti-bot header — the frontend sends a secret handshake value
    admin_key: str = Field(..., min_length=1)


# ── Response shapes ───────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds until expiry


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    avatar_url: str | None
    widget_config: dict
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MessageResponse(BaseModel):
    message: str
