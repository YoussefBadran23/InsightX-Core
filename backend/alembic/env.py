"""
Alembic environment — wired to InsightX models for autogenerate support.
DATABASE_URL is read from the .env file, not hard-coded in alembic.ini.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────────
# Add the backend/app directory to sys.path so our models can be imported.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load DATABASE_URL from backend/.env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ── Alembic config ─────────────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url with value from environment (not alembic.ini)
database_url = os.getenv(
    "DATABASE_URL",
    "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db",
)
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import all models so autogenerate can detect them ─────────────────────────
from app.database import Base  # noqa: E402
import app.models  # noqa: E402 — triggers all model imports via __init__.py

target_metadata = Base.metadata


# ── Migration runners ─────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (e.g. CI diff generation)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,      # Detect column type changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
