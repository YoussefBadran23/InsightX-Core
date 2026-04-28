"""Optimized Shared infrastructure for all analytics modules."""
import os
import time
import logging
import functools
import json
from datetime import date, datetime
from decimal import Decimal
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from celery_app import celery_app

logger = logging.getLogger(__name__)

_UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")

# Optimization: Single engine instance with connection pooling
_engine = create_engine(_DATABASE_URL, pool_size=10, max_overflow=20, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine)

def load_parquet(job_id: str, columns: list[str] = None) -> pd.DataFrame:
    """Load cleaned Parquet with column pruning to save RAM."""
    path = os.path.join(_UPLOAD_DIR, "cleaned", f"{job_id}_cleaned.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Parquet not found: {path}")
    
    # RAM Optimization: Only load columns actually needed by the module
    df = pd.read_parquet(path, columns=columns)
    logger.info(f"Loaded {len(df)} rows for job {job_id}. RAM optimized: {columns is not None}")
    return df

def sanitize_json(obj):
    """Deeply convert types for JSON compatibility, handling PD/NP edge cases."""
    if obj is None:
        return None
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float, Decimal)):
        return round(float(obj), 2)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (pd.Period, bool, np.bool_)):
        if isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        return str(obj)
    return obj

def upsert_result(session, job_id: str, analysis_type: str, result_json: dict, duration_ms: int):
    """UPSERT analysis results using high-performance JSONB."""
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
                is_stale = FALSE, 
                duration_ms = EXCLUDED.duration_ms
        """),
        {
            "atype": analysis_type, 
            "job_id": job_id, 
            "rjson": json.dumps(result_json), 
            "dur": duration_ms
        }
    )
    session.commit()

def analytics_task(module_key: str, analysis_type: str, required_cols: list[str] = None):
    """Optimized decorator with automatic memory and status management."""
    def decorator(fn):
        @celery_app.task(name=f"tasks.analytics.{module_key}", bind=True, max_retries=1, queue="analytics")
        @functools.wraps(fn)
        def wrapper(self, job_id: str):
            session = SessionLocal()
            try:
                # 1. Update Status to Running
                session.execute(
                    text("UPDATE analytics_module_status SET run_status='running', updated_at=NOW() "
                         "WHERE upload_job_id=:j AND module_key=:m"),
                    {"j": job_id, "m": module_key}
                )
                session.commit()

                # 2. Optimized Data Loading
                df = load_parquet(job_id, columns=required_cols)
                
                # 3. Execution and Timing
                t0 = time.time()
                result = fn(df, session, job_id)
                duration_ms = int((time.time() - t0) * 1000)

                # 4. Save and Update Status to Completed
                upsert_result(session, job_id, analysis_type, sanitize_json(result), duration_ms)
                session.execute(
                    text("UPDATE analytics_module_status SET run_status='completed', updated_at=NOW() "
                         "WHERE upload_job_id=:j AND module_key=:m"),
                    {"j": job_id, "m": module_key}
                )
                session.commit()
                return {"status": "success", "module": module_key}
            except Exception as exc:
                session.rollback()
                logger.error(f"Task {module_key} failed: {exc}", exc_info=True)
                session.execute(
                    text("UPDATE analytics_module_status SET run_status='failed', error_message=:e, updated_at=NOW() "
                         "WHERE upload_job_id=:j AND module_key=:m"),
                    {"j": job_id, "m": module_key, "e": str(exc)[:499]}
                )
                session.commit()
                raise self.retry(exc=exc, countdown=10)
            finally:
                session.close()
        return wrapper
    return decorator

def has_col(df: pd.DataFrame, col: str) -> bool:
    """Check if a column exists and is not entirely null."""
    return col in df.columns and df[col].notna().any()

def to_month_str(dt) -> str:
    """Safe conversion to YYYY-MM strings."""
    if isinstance(dt, pd.Period):
        return str(dt)
    if isinstance(dt, (pd.Timestamp, datetime, date)):
        return dt.strftime("%Y-%m")
    return str(dt)