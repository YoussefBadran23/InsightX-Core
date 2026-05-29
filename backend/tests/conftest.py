"""
Shared pytest fixtures for InsightX backend tests.

- SQLite in-memory database (test isolation, no live Postgres needed)
- FastAPI TestClient with all dependencies overridden
- slowapi rate limiter disabled
- Celery tasks never dispatched (mocked at the call site)
- Factory helpers for every domain entity
"""

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# ── App imports ───────────────────────────────────────────────────────────────
# Patch Sentry and ddtrace at import time so they don't blow up in tests
# (these packages may not be installed in the test environment)
import sys
import types
import unittest.mock as mock

def _stub_module(name: str):
    """Insert a no-op stub for an optional monitoring package."""
    if name not in sys.modules:
        mod = types.ModuleType(name)
        sys.modules[name] = mod

for _pkg in ("sentry_sdk", "ddtrace"):
    _stub_module(_pkg)

# Provide the specific attributes main.py uses before it is imported
import sys as _sys
_sentry = _sys.modules["sentry_sdk"]
if not hasattr(_sentry, "init"):
    _sentry.init = lambda *a, **kw: None  # type: ignore

_dd = _sys.modules["ddtrace"]
if not hasattr(_dd, "patch_all"):
    _dd.patch_all = lambda *a, **kw: None  # type: ignore
if not hasattr(_dd, "tracer"):
    _tracer_stub = types.SimpleNamespace(configure=lambda **kw: None)
    _dd.tracer = _tracer_stub  # type: ignore

from app.main import app
from app.database import Base, get_db

# ── SQLite JSONB / UUID shim ──────────────────────────────────────────────────
# PostgreSQL-specific column types (JSONB, UUID(as_uuid=True)) cannot be
# rendered or processed correctly by SQLite. We patch:
#   1. The SQLite DDL compiler so CREATE TABLE succeeds.
#   2. The PostgreSQL UUID type so bind/result processors handle string UUIDs
#      that SQLite stores and returns as VARCHAR(36).
import uuid as _uuid_mod
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler as _STC
from sqlalchemy.dialects.postgresql import UUID as _PG_UUID
from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB

# 1. DDL rendering
def _visit_JSONB(self, type_, **kw):
    return "JSON"

def _visit_UUID_ddl(self, type_, **kw):
    return "VARCHAR(36)"

_STC.visit_JSONB = _visit_JSONB          # type: ignore[attr-defined]
_STC.visit_UUID  = _visit_UUID_ddl        # type: ignore[attr-defined]

# 2. Bind/result value processing for UUID columns under SQLite.
#    PostgreSQL's UUID type calls value.hex on bind (expects uuid.UUID objects)
#    and returns UUID objects on result. SQLite stores/returns plain strings so
#    we replace the processors with string-safe versions.
_orig_bind = _PG_UUID.bind_processor

def _uuid_bind_processor(self, dialect):
    if dialect.name != "sqlite":
        return _orig_bind(self, dialect)
    def process(value):
        if value is None:
            return None
        if isinstance(value, _uuid_mod.UUID):
            return str(value)
        return str(value)
    return process

_PG_UUID.bind_processor = _uuid_bind_processor  # type: ignore[method-assign]

_orig_result = _PG_UUID.result_processor

def _uuid_result_processor(self, dialect, coltype):
    if dialect.name != "sqlite":
        return _orig_result(self, dialect, coltype)
    def process(value):
        if value is None:
            return None
        if isinstance(value, _uuid_mod.UUID):
            return value
        return _uuid_mod.UUID(str(value))
    return process

_PG_UUID.result_processor = _uuid_result_processor  # type: ignore[method-assign]

from app.models.user import User
from app.models.upload_job import UploadJob
from app.models.customer import Customer
from app.models.product import Product
from app.models.daily_kpi_snapshot import DailyKpiSnapshot
from app.models.analysis_results_cache import AnalysisResultsCache
from app.models.analytics_module_status import AnalyticsModuleStatus
from app.core.security import hash_password, create_access_token

# ── SQLite in-memory engine ───────────────────────────────────────────────────
# SQLite "sqlite://" creates a NEW database per connection, so tables created
# on one connection are invisible to others. The fix: use a single underlying
# sqlite3 connection and tell SQLAlchemy to always reuse it via creator=.

import sqlite3 as _sqlite3
from sqlalchemy.pool import StaticPool

# SQLite ":memory:" creates a separate DB per connection. To share one database
# across all ORM sessions and the FastAPI TestClient, we create one raw
# sqlite3 connection at module-level and tell SQLAlchemy to always return
# THAT connection via the creator= argument. StaticPool + creator= together
# ensure only one DBAPI connection ever exists for this engine.
_RAW_CONN = _sqlite3.connect(":memory:", check_same_thread=False)
_RAW_CONN.execute("PRAGMA foreign_keys=ON")
_RAW_CONN.commit()

engine = create_engine(
    "sqlite+pysqlite://",
    creator=lambda: _RAW_CONN,
    poolclass=StaticPool,
    echo=False,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Table creation ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all ORM tables once for the entire test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ── Per-test DB session ───────────────────────────────────────────────────────

@pytest.fixture()
def db(create_tables) -> Generator[Session, None, None]:
    """
    Yield a DB session isolated per test.

    All sessions share the same raw sqlite3 connection (_RAW_CONN).
    We truncate all tables before each test, yield the session, then
    roll back any uncommitted work. We expunge the session without
    closing the underlying connection.
    """
    _truncate_all()
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        try:
            session.rollback()
        except Exception:
            pass
        session.expunge_all()
        # Don't call session.close() — that would close _RAW_CONN via the pool.


def _truncate_all() -> None:
    """Delete all rows from every table via the raw connection."""
    _RAW_CONN.execute("PRAGMA foreign_keys=OFF")
    for table in reversed(Base.metadata.sorted_tables):
        _RAW_CONN.execute(f"DELETE FROM {table.name}")
    _RAW_CONN.execute("PRAGMA foreign_keys=ON")
    _RAW_CONN.commit()


# ── FastAPI TestClient ────────────────────────────────────────────────────────

@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    """
    Return a synchronous TestClient with:
    - get_db overridden to use the test SQLite session
    - slowapi limiter replaced with a no-op mock
    - lifespan disabled (tables already created; no Alembic, no sentence-transformers)
    """

    def override_get_db():
        try:
            yield db
        finally:
            pass  # session lifecycle managed by `db` fixture

    app.dependency_overrides[get_db] = override_get_db

    # Disable rate limiter: replace with a mock that never raises
    _real_limiter = app.state.limiter
    noop_limiter = MagicMock()
    noop_limiter.limit = lambda *a, **kw: (lambda f: f)  # decorator passthrough
    app.state.limiter = noop_limiter

    # Disable the app lifespan so Alembic and sentence-transformers don't run.
    # We replace the lifespan with a no-op async context manager.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.router.lifespan_context = original_lifespan

    app.dependency_overrides.clear()
    app.state.limiter = _real_limiter


# ── Auth helpers ──────────────────────────────────────────────────────────────

TEST_USER_EMAIL = "testuser@example.com"
TEST_USER_PASSWORD = "Test@Password1"


@pytest.fixture()
def test_user(db: Session) -> User:
    """Create and return a persisted test user."""
    user = User(
        email=TEST_USER_EMAIL,
        full_name="Test User",
        hashed_password=hash_password(TEST_USER_PASSWORD),
        role="user",
        widget_config={},
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def auth_headers(test_user: User) -> dict:
    """Return Authorization headers with a valid JWT for test_user."""
    token, _ = create_access_token(
        subject=str(test_user.id),
        extra_claims={"role": test_user.role, "email": test_user.email},
    )
    return {"Authorization": f"Bearer {token}"}


# ── Entity factories ──────────────────────────────────────────────────────────

def make_upload_job(db: Session, user_id: uuid.UUID, **kwargs) -> UploadJob:
    defaults = dict(
        user_id=user_id,
        s3_key="test_file.csv",
        original_filename="test_file.csv",
        status="completed",
        source_currency="USD",
        rows_processed=100,
        rows_failed=0,
        completed_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    job = UploadJob(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def make_customer(db: Session, user_id: uuid.UUID, **kwargs) -> Customer:
    uid = uuid.uuid4().hex[:8]
    defaults = dict(
        user_id=user_id,
        external_id=f"CUS-{uid}",
        email=f"customer-{uid}@example.com",
        full_name=f"Customer {uid}",
        lifetime_value=Decimal("500.00"),
        total_orders=5,
        deleted_at=None,
    )
    defaults.update(kwargs)
    customer = Customer(**defaults)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def make_product(db: Session, user_id: uuid.UUID, **kwargs) -> Product:
    uid = uuid.uuid4().hex[:8]
    defaults = dict(
        user_id=user_id,
        sku=f"SK-{uid}",
        name=f"Product {uid}",
        category="Electronics",
        total_revenue=Decimal("1000.00"),
        total_units_sold=50,
        unit_price=Decimal("20.00"),
        stock_qty=100,
        low_stock_threshold=10,
        is_active=True,
        deleted_at=None,
    )
    defaults.update(kwargs)
    product = Product(**defaults)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def make_kpi_snapshot(
    db: Session,
    user_id: uuid.UUID,
    snapshot_date: date | None = None,
    **kwargs,
) -> DailyKpiSnapshot:
    defaults = dict(
        user_id=user_id,
        snapshot_date=snapshot_date or date.today(),
        total_revenue=Decimal("10000.00"),
        active_customers=200,
        new_customers=20,
        total_orders=150,
        avg_order_value=Decimal("66.67"),
        churn_rate=Decimal("0.0240"),
        revenue_na=Decimal("5000.00"),
        revenue_eu=Decimal("3000.00"),
        revenue_apac=Decimal("1500.00"),
        revenue_latam=Decimal("500.00"),
    )
    defaults.update(kwargs)
    snap = DailyKpiSnapshot(**defaults)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def make_analytics_result(
    db: Session,
    upload_job_id: uuid.UUID,
    analysis_type: str = "A01_revenue_summary",
    result_data: dict | None = None,
    **kwargs,
) -> AnalysisResultsCache:
    if result_data is None:
        result_data = {"total": 99999, "currency": "USD"}
    defaults = dict(
        upload_job_id=upload_job_id,
        analysis_type=analysis_type,
        result_json=result_data,
        computed_at=datetime.now(timezone.utc),
        is_stale=False,
        duration_ms=100,
    )
    defaults.update(kwargs)
    result = AnalysisResultsCache(**defaults)
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def make_module_status(
    db: Session,
    upload_job_id: uuid.UUID,
    module_key: str = "A01_revenue_summary",
    **kwargs,
) -> AnalyticsModuleStatus:
    defaults = dict(
        upload_job_id=upload_job_id,
        module_key=module_key,
        module_name="Revenue Summary",
        module_name_ar="ملخص الإيرادات",
        description="Summarises revenue over time.",
        can_run=True,
        queue="analytics",
        run_status="completed",
    )
    defaults.update(kwargs)
    ms = AnalyticsModuleStatus(**defaults)
    db.add(ms)
    db.commit()
    db.refresh(ms)
    return ms


# ── Expose factories as fixtures too ─────────────────────────────────────────

@pytest.fixture()
def make_job(db: Session, test_user: User):
    def _factory(**kwargs):
        return make_upload_job(db, test_user.id, **kwargs)
    return _factory


@pytest.fixture()
def make_cust(db: Session, test_user: User):
    def _factory(**kwargs):
        return make_customer(db, test_user.id, **kwargs)
    return _factory


@pytest.fixture()
def make_prod(db: Session, test_user: User):
    def _factory(**kwargs):
        return make_product(db, test_user.id, **kwargs)
    return _factory


@pytest.fixture()
def make_snap(db: Session, test_user: User):
    def _factory(snapshot_date=None, **kwargs):
        return make_kpi_snapshot(db, test_user.id, snapshot_date=snapshot_date, **kwargs)
    return _factory


@pytest.fixture()
def make_analysis(db: Session):
    def _factory(upload_job_id, analysis_type="A01_revenue_summary", result_data=None, **kwargs):
        return make_analytics_result(db, upload_job_id, analysis_type, result_data, **kwargs)
    return _factory
