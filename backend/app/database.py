"""Database engine, session factory, and Base for SQLAlchemy models."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db",
)

# Sync engine — used by Alembic migrations and Celery workers.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # Detect stale connections before use
    pool_size=10,
    max_overflow=20,
    echo=os.getenv("APP_ENV", "development") == "development",
)

# Session factory — used by FastAPI dependency injection.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""
    pass


def get_db():
    """FastAPI dependency: yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
