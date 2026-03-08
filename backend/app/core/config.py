"""Application settings loaded from environment variables via pydantic-settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"

    # Admin secret key — frontend sends this on the ESC admin login panel.
    # Set a strong random value in production .env
    ADMIN_SECRET_KEY: str = "insightx-admin-secret-change-me"

    # JWT
    SECRET_KEY: str = "insecure-change-me-in-production"
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

    # Groq
    GROQ_API_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance (one per process)."""
    return Settings()


settings = get_settings()
