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

    # Database (PostgreSQL for core data)
    DATABASE_URL: str = (
        "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db"
    )

    # MongoDB (Student Cluster for scraped data)
    MONGO_URL: str = "mongodb://localhost:27017/insightx_scraped"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "insightx-raw-data-lake-dev"

    # Local LLM Support (Ollama)
    LOCAL_LLM_URL: str = "http://host.docker.internal:11434/v1"
    LOCAL_LLM_API_KEY: str = "ollama"
    LOCAL_LLM_MODEL: str = "qwen2.5-coder:7b"

    # Frontend URL (CORS whitelist)
    FRONTEND_URL: str = ""

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 100

    # MongoDB Atlas (For scraped data)
    MONGO_URL: str = "mongodb://localhost:27017/insightx_scraped"

    # Monitoring
    SENTRY_DSN: str = ""  # For error tracking
    DD_API_KEY: str = ""  # Datadog API key
    DD_SERVICE: str = "insightx-backend"
    DD_ENV: str = "development"

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
