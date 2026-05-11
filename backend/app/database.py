"""Database engine, session factory, and Base for SQLAlchemy models."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
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

# MongoDB — lazy initialisation so a missing Mongo instance does NOT crash
# the backend at startup. Call get_mongo_db() only where Mongo is needed.
_mongo_client = None
_mongo_db = None

def get_mongo_db():
    """Return the MongoDB database handle, creating the client on first call."""
    global _mongo_client, _mongo_db
    if _mongo_db is None:
        try:
            from pymongo import MongoClient
            _mongo_client = MongoClient(settings.MONGO_URL, serverSelectionTimeoutMS=3000)
            _mongo_db = _mongo_client.get_database()
        except Exception as e:
            import logging
            logging.getLogger("insightx.db").warning(
                "MongoDB unavailable — scraped-data features disabled. %s", e
            )
    return _mongo_db

# Keep backwards-compatible aliases so existing code that does
# `from app.database import mongo_db` still imports without crashing.
# They will be None until get_mongo_db() is first called successfully.
mongo_client = None
mongo_db = None

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session and ensures reliable cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()