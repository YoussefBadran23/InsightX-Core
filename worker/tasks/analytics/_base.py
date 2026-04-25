"""Shared infrastructure for all analytics modules (A01-A14).

Provides:
- load_parquet(job_id) → pd.DataFrame
- sanitize_json(obj)  → JSON-safe dict/list
- upsert_result(...)  → INSERT ON CONFLICT into analysis_results_cache
- update_module_status(...)
- @analytics_task decorator that wires all of the above together
"""

import os
import time
import logging
import functools
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from celery_app import celery_app

logger = logging.getLogger(__name__)

_UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://insightx_user:insightx_pass@db:5432/insightx_db",
)

_engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine)


# ── Parquet loader ──────────────────────────────────────────────────────────

def load_parquet(job_id: str) -> pd.DataFrame:
    """Load the cleaned Parquet produced by Stage 3."""
    path = os.path.join(_UPLOAD_DIR, "cleaned", f"{job_id}_cleaned.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cleaned parquet not found: {path}")
    df = pd.read_parquet(path)
    logger.info("Loaded parquet for job %s — %d rows, %d cols", job_id, len(df), len(df.columns))
    return df


# ── JSON sanitiser ──────────────────────────────────────────────────────────

def sanitize_json(obj):
    """Recursively convert numpy/pandas types to JSON-safe Python primitives."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return round(float(obj), 2)
    if isinstance(obj, Decimal):
        return round(float(obj), 2)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, pd.Period):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return [sanitize_json(v) for v in obj.tolist()]
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj


# ── DB helpers ──────────────────────────────────────────────────────────────

def upsert_result(session, job_id: str, analysis_type: str, result_json: dict, duration_ms: int):
    """INSERT or UPDATE a row in analysis_results_cache."""
    session.execute(
        text("""
            INSERT INTO analysis_results_cache
                (id, analysis_type, upload_job_id, result_json, computed_at, is_stale, duration_ms)
            VALUES
                (gen_random_uuid(), :atype, :job_id, :rjson::jsonb, NOW(), FALSE, :dur)
            ON CONFLICT (analysis_type, upload_job_id)
            DO UPDATE SET
                result_json = EXCLUDED.result_json,
                computed_at = EXCLUDED.computed_at,
                is_stale    = FALSE,
                duration_ms = EXCLUDED.duration_ms
        """),
        {
            "atype": analysis_type,
            "job_id": job_id,
            "rjson": __import__("json").dumps(result_json, default=str),
            "dur": duration_ms,
        },
    )
    session.commit()


def update_module_status(session, job_id: str, module_key: str, status: str, error: str | None = None):
    """Update run_status (and optional error_message) on analytics_module_status."""
    params = {"job_id": job_id, "mkey": module_key, "status": status, "err": error}
    session.execute(
        text("""
            UPDATE analytics_module_status
            SET run_status    = :status,
                error_message = :err,
                updated_at    = NOW()
            WHERE upload_job_id = :job_id
              AND module_key    = :mkey
        """),
        params,
    )
    session.commit()


# ── Decorator ───────────────────────────────────────────────────────────────

def analytics_task(module_key: str, analysis_type: str):
    """Decorator factory that wraps a pure analysis function into a full Celery task.

    The wrapped function signature must be:  fn(df, session, job_id) → dict
    """

    def decorator(fn):
        @celery_app.task(
            name=f"tasks.analytics.{module_key}",
            bind=True,
            max_retries=1,
            queue="analytics",
        )
        @functools.wraps(fn)
        def wrapper(self, job_id: str):
            session = SessionLocal()
            t0 = time.time()
            try:
                update_module_status(session, job_id, module_key, "running")
                df = load_parquet(job_id)
                result = fn(df, session, job_id)
                result = sanitize_json(result)
                duration_ms = int((time.time() - t0) * 1000)
                upsert_result(session, job_id, analysis_type, result, duration_ms)
                update_module_status(session, job_id, module_key, "completed")
                logger.info("Job %s: %s completed in %dms", job_id, module_key, duration_ms)
                return {"status": "completed", "module": module_key, "duration_ms": duration_ms}
            except Exception as exc:
                logger.error("Job %s: %s failed — %s", job_id, module_key, exc, exc_info=True)
                try:
                    update_module_status(session, job_id, module_key, "failed", str(exc)[:500])
                except Exception:
                    pass
                raise self.retry(exc=exc, countdown=30)
            finally:
                session.close()

        # Preserve reference so __init__.py can import it
        wrapper._analytics_module_key = module_key
        return wrapper

    return decorator


# ── Column helpers ──────────────────────────────────────────────────────────

def has_col(df: pd.DataFrame, col: str) -> bool:
    """Check if a column exists and has at least one non-null value."""
    return col in df.columns and df[col].notna().any()


def to_month_str(dt) -> str:
    """Convert a date-like value to 'YYYY-MM' string."""
    if isinstance(dt, pd.Period):
        return str(dt)
    if isinstance(dt, (pd.Timestamp, datetime, date)):
        return dt.strftime("%Y-%m")
    return str(dt)
