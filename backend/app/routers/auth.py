"""Auth router — register, login, forgot-password, reset-password, /me."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_reset_token,
    hash_reset_token,
)
from app.core.config import settings
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    AdminLoginRequest,
    TokenResponse,
    UserResponse,
    RegisterResponse,
    MessageResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Helper ────────────────────────────────────────────────────────────────────

def _user_to_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


# ── POST /auth/register ────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user.
    Returns the created user object + a ready-to-use JWT access token
    so the client can proceed without a separate login step.
    """
    # Check email uniqueness
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
        widget_config={},
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token, expires_in = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role, "email": user.email},
    )

    return RegisterResponse(
        user=_user_to_response(user),
        access_token=token,
        expires_in=expires_in,
    )


# ── POST /auth/login ───────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT access token",
)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email + password.
    Returns a JWT access token. Stamps last_login_at on success.
    Deliberately vague error message to prevent user-enumeration attacks.
    """
    user = (
        db.query(User)
        .filter(User.email == body.email, User.deleted_at.is_(None))
        .first()
    )

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact support.",
        )

    # Stamp last login
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token, expires_in = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role, "email": user.email},
    )

    return TokenResponse(access_token=token, expires_in=expires_in)


# ── GET /auth/me ───────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the currently authenticated user's profile",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the profile for the currently authenticated user."""
    return _user_to_response(current_user)


# ── PATCH /auth/me ─────────────────────────────────────────────────────────────

@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update the current user's profile (name, avatar)",
)
def update_me(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update mutable profile fields (full_name, avatar_url)."""
    allowed = {"full_name", "avatar_url"}
    for key, value in body.items():
        if key in allowed:
            setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return _user_to_response(current_user)


# ── POST /auth/change-password ─────────────────────────────────────────────────

@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password for authenticated user",
)
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify current password, then set the new one."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = hash_password(body.new_password)
    db.commit()
    return MessageResponse(message="Password updated successfully")


# ── POST /auth/forgot-password ─────────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset link",
)
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Generate a password reset token and store its hash.
    Always returns 200 (even if email not found) to prevent user enumeration.
    In production, the raw token is emailed to the user.
    """
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        raw_token, hashed_token = generate_reset_token()
        user.reset_token = hashed_token
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.RESET_TOKEN_EXPIRE_MINUTES
        )
        db.commit()
        # TODO (Phase 3): send email with reset link containing raw_token
        # For now, the raw token is returned in the message for development
        return MessageResponse(
            message=f"[DEV] Reset token: {raw_token} — expires in {settings.RESET_TOKEN_EXPIRE_MINUTES} min"
        )

    # Same response for non-existent emails (prevents user enumeration)
    return MessageResponse(
        message="If an account with that email exists, a reset link has been sent"
    )


# ── POST /auth/reset-password ──────────────────────────────────────────────────

@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a valid reset token",
)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Consume a password reset token.
    Token is validated against the stored hash and expiry timestamp.
    """
    hashed_incoming = hash_reset_token(body.token)

    user = db.query(User).filter(User.reset_token == hashed_incoming).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if (
        user.reset_token_expires_at is None
        or user.reset_token_expires_at < datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new one.",
        )

    user.hashed_password = hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.commit()

    return MessageResponse(message="Password reset successfully. You can now log in.")


# ── POST /auth/admin/login ─────────────────────────────────────────────────────
# Secret endpoint — NOT listed in the normal register/login flow.
# Triggered only from the ESC-key admin panel on the frontend.
# Two-layer security: correct password + correct ADMIN_SECRET_KEY.

@router.post(
    "/admin/login",
    response_model=TokenResponse,
    summary="[SECRET] Admin login — requires admin_key handshake",
    include_in_schema=False,   # Hidden from the public Swagger docs
)
def admin_login(body: AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Secret admin login endpoint.
    Called by the ESC-triggered admin panel on the frontend.

    Two security layers:
    1. body.admin_key must match settings.ADMIN_SECRET_KEY
    2. The user must have role='admin'
    """
    # Layer 1 — validate the secret handshake key
    if body.admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    # Layer 2 — validate credentials
    user = (
        db.query(User)
        .filter(
            User.email == body.email,
            User.role == "admin",
            User.deleted_at.is_(None),
        )
        .first()
    )

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token, expires_in = create_access_token(
        subject=str(user.id),
        extra_claims={"role": "admin", "email": user.email},
    )

    return TokenResponse(access_token=token, expires_in=expires_in)
