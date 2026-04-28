"""Database engine, session factory, and Base for SQLAlchemy models."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from pymongo import MongoClient
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

# Sync engine — used by Alembic migrations, FastAPI, and Celery workers.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # Detect stale connections before use
    pool_size=5,              # Lowered to 5 to prevent maxing out PostgreSQL limits
    max_overflow=10,          # Extra connections allowed during traffic spikes
    pool_timeout=30,          # Wait up to 30 seconds for an available connection
    pool_recycle=1800,        # Recycle connections every 30 minutes to prevent timeouts
    echo=(settings.APP_ENV == "development"),
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

# MongoDB client for scraped data
mongo_client = MongoClient(settings.MONGO_URL)
mongo_db = mongo_client.get_database()

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session and ensures reliable cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()