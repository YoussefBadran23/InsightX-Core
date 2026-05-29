"""Application settings loaded from environment variables via pydantic-settings."""

import sys
from functools import lru_cache
from pydantic_settings import BaseSettings

_WEAK_SECRETS = {
    "insightx-admin-secret-change-me",
    "insecure-change-me-in-production",
    "dev-secret-key-replace-in-production",
    "dev-admin-key-replace-in-production",
    "change_me_to_a_long_random_string",
    "9a3b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b",
    "1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a",
}


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Admin secret key — frontend sends this on the ESC admin login panel.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    ADMIN_SECRET_KEY: str = "dev-admin-key-replace-in-production"

    # JWT — generate with: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = "dev-secret-key-replace-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # Database (PostgreSQL — single source of truth for all data)
    DATABASE_URL: str = (
        "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db"
    )

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # AWS S3 removed 2026-05-14 — DigitalOcean Spaces is the eventual storage
    # backend if/when object storage is needed. Add settings here when wiring
    # that up; the codebase currently stores uploads on local disk + Postgres.

    # Local LLM removed 2026-05-14 — to be wired up later when the insights
    # generation pipeline lands. Add LLM_URL / LLM_API_KEY / LLM_MODEL here
    # when that work begins.

    # Frontend URL (CORS whitelist)
    FRONTEND_URL: str = ""

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 100

    # Monitoring
    SENTRY_DSN: str = ""  # For error tracking
    DD_API_KEY: str = ""  # Datadog API key
    DD_SERVICE: str = "insightx-backend"
    DD_ENV: str = "development"

    # SMTP / Email — used by /auth/forgot-password to send reset links.
    # When SMTP_USER or SMTP_PASSWORD is empty, the email module skips the
    # real send and prints the reset link to the backend logs instead
    # (dev-friendly fallback).
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_NAME: str = "InsightX"
    EMAILS_FROM_EMAIL: str = "noreply@insightx.local"
    # Brand-consistent support address — used as From: on password reset emails
    # and any future transactional mail. Override in .env for production.
    SUPPORT_EMAIL: str = "support@insightx.io"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance (one per process)."""
    s = Settings()
    if s.APP_ENV == "production":
        if s.SECRET_KEY in _WEAK_SECRETS or len(s.SECRET_KEY) < 32:
            print(
                "FATAL: SECRET_KEY is weak or a placeholder. "
                "Set a strong value (>=32 chars) in .env before running in production.",
                file=sys.stderr,
            )
            sys.exit(1)
        if s.ADMIN_SECRET_KEY in _WEAK_SECRETS or len(s.ADMIN_SECRET_KEY) < 32:
            print(
                "FATAL: ADMIN_SECRET_KEY is weak or a placeholder. "
                "Set a strong value (>=32 chars) in .env before running in production.",
                file=sys.stderr,
            )
            sys.exit(1)
    return s


settings = get_settings()
