"""Database engine, session factory, and Base for SQLAlchemy models.

PostgreSQL is the single source of truth for all data. MongoDB was removed
on 2026-05-14 in favour of a Postgres-only stack — see commit notes.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

# Sync engine — used by Alembic migrations, FastAPI, and Celery workers.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    echo=False,
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


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session and ensures reliable cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
