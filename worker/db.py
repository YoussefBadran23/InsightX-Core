"""
Database configuration for the InsightX Worker.
Provides a single shared connection pool across all Celery tasks.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Uses the same connection string as the backend
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://insightx_user:insightx_pass@db:5432/insightx_db"
)

# A single engine for the worker process, avoiding the 'Too many connections' error
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    """Returns a new DB session. Callers must close it."""
    return SessionLocal()
