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
}


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"

    # Admin secret key — frontend sends this on the ESC admin login panel.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    ADMIN_SECRET_KEY: str = "dev-admin-key-replace-in-production"

    # JWT — generate with: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = "dev-secret-key-replace-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    DATABASE_URL: str = (
        "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db"
    )

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "insightx-raw-data-lake-prod"

    # Local LLM Support (LM Studio / Ollama)
    LOCAL_LLM_URL: str = "http://host.docker.internal:1234/v1"
    LOCAL_LLM_API_KEY: str = "lm-studio"

    # Frontend URL (CORS whitelist)
    FRONTEND_URL: str = ""

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 100

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
