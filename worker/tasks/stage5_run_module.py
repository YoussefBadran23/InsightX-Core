"""Stage 5 — Generic analytics module dispatcher.

One Celery task that can run ANY registered analytics module. Replaces the
old "one task per module" pattern, which required wrapping each `run(df)`
function with `@celery_app.task`. Now the analytics modules stay pure
(testable via `run_analytics.py` CLI) and this task is the only place that
talks to Celery, the DB, and the parquet on disk.

Flow per call:
    1. Look up `schema.MODULES[module_key]` — pure-function pointer + metadata.
    2. Mark `analytics_module_status.run_status = 'running'`.
    3. Load only the columns this module declared (`required ∪ optional`).
    4. Call `module.fn(df)`, time it.
    5. Sanitize result for JSON, upsert into `analysis_results_cache`.
    6. Mark `analytics_module_status.run_status = 'completed'`.

Errors:
    - If the module key isn't registered or has no `fn`, we mark `skipped`
      (not `failed`) with reason `not_implemented`. The chord still
      succeeds and the pipeline finalizes — examiners see a clean state.
    - Any exception inside `module.fn(df)` marks `failed`, persists the
      error, and re-raises so Celery's retry/dead-letter logic engages.

Why one task instead of N:
    - Lower Celery overhead per module (no per-task registration / pickling
      of decorator state).
    - Modules can be added without touching Celery config — just write the
      `@register`'d `run(df)` and it's instantly dispatchable.
    - The same task can be invoked manually from a Python shell or pytest
      with no celery_app at all (call .run() directly).
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any

import io

import pandas as pd
import redis as redis_lib
from celery import shared_task
from sqlalchemy import text

from db import get_db_session
import schema
from tasks.analytics._base import sanitize_json

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
CLEANED_DIR = os.path.join(UPLOAD_DIR, "cleaned")

# ── Redis parquet cache ──────────────────────────────────────────────────────
# All 39 modules run concurrently and read the SAME parquet file. Without
# caching that's 39 separate disk reads. We cache the raw bytes in Redis
# (key: parquet:<job_id>, TTL 2h) so only the first module pays the disk I/O.
_REDIS_CLIENT: redis_lib.Redis | None = None
_PARQUET_TTL = 7200  # 2 hours


def _redis() -> redis_lib.Redis:
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        _REDIS_CLIENT = redis_lib.Redis.from_url(url, socket_timeout=2)
    return _REDIS_CLIENT


def _get_parquet_bytes(job_id: str) -> bytes:
    """Return raw parquet bytes from Redis cache, falling back to disk."""
    cache_key = f"parquet:{job_id}"
    try:
        cached = _redis().get(cache_key)
        if cached:
            return cached
    except Exception:
        pass  # Redis unavailable — fall through to disk

    path = os.path.join(CLEANED_DIR, f"{job_id}.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Parquet not found: {path}")
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        _redis().setex(cache_key, _PARQUET_TTL, data)
    except Exception:
        pass  # cache write failure is non-fatal
    return data


def _set_status(db, job_id: str, module_key: str,
                run_status: str, error_message: str | None = None) -> None:
    """Update one analytics_module_status row. Safe under chord parallelism."""
    db.execute(
        text("""
            UPDATE analytics_module_status
               SET run_status = :st,
                   error_message = :err,
                   updated_at = NOW()
             WHERE upload_job_id = :jid
               AND module_key = :mk
        """),
        {"st": run_status, "err": (error_message or "")[:499] or None,
         "jid": job_id, "mk": module_key},
    )
    db.commit()


def _upsert_result(db, job_id: str, analysis_type: str,
                   result_json: dict, duration_ms: int) -> None:
    """UPSERT into analysis_results_cache. Idempotent on re-runs.

    Note: we use CAST(... AS jsonb) instead of `::jsonb` because SQLAlchemy's
    text() parses `:param::type` as a single token and throws a syntax error.
    """
    import json
    db.execute(
        text("""
            INSERT INTO analysis_results_cache
                (id, analysis_type, upload_job_id, result_json,
                 computed_at, is_stale, duration_ms)
            VALUES
                (gen_random_uuid(), :atype, :jid, CAST(:rjson AS jsonb),
                 NOW(), FALSE, :dur)
            ON CONFLICT (analysis_type, upload_job_id)
            DO UPDATE SET
                result_json = EXCLUDED.result_json,
                computed_at = EXCLUDED.computed_at,
                is_stale = FALSE,
                duration_ms = EXCLUDED.duration_ms
        """),
        {"atype": analysis_type, "jid": job_id,
         "rjson": json.dumps(result_json), "dur": duration_ms},
    )
    db.commit()


def _load_parquet(job_id: str, module: schema.AnalyticsModule) -> pd.DataFrame:
    """Load only the columns this module declared. Uses Redis cache so the
    parquet file is read from disk at most once per job across all 39 modules."""
    import pyarrow.parquet as pq

    raw = _get_parquet_bytes(job_id)
    buf = io.BytesIO(raw)

    wanted = set(module.required_cols) | set(module.optional_cols)
    if wanted:
        schema_cols = set(pq.read_schema(buf).names)
        buf.seek(0)
        cols = list(wanted & schema_cols) or None
    else:
        cols = None

    buf.seek(0)
    return pd.read_parquet(buf, columns=cols)


@shared_task(name="tasks.analytics.run_module", bind=True, max_retries=1)
def run_module(self, job_id: str, module_key: str) -> dict:
    """Dispatch one analytics module by key.

    Called as a chord header — Celery does NOT inject previous results into
    chord *children* (only into the callback), so the signature is the
    plain (job_id, module_key) pair. Invoke directly with
    `run_module.delay(job_id, key)` for manual testing.
    """
    db = get_db_session()
    try:
        module = schema.MODULES.get(module_key)

        # Unknown or unimplemented module → skip cleanly.
        if module is None:
            _set_status(db, job_id, module_key, "skipped",
                        "module_key not in schema.MODULES")
            return {"status": "skipped", "module_key": module_key,
                    "reason": "unknown_key"}
        if module.fn is None:
            _set_status(db, job_id, module_key, "skipped",
                        "module not implemented yet")
            return {"status": "skipped", "module_key": module_key,
                    "reason": "not_implemented"}

        _set_status(db, job_id, module_key, "running")

        # Load → execute → time.
        df = _load_parquet(job_id, module)
        t0 = time.time()
        try:
            result = module.fn(df)
        except Exception as exc:
            duration_ms = int((time.time() - t0) * 1000)
            logger.exception(f"Module {module_key} crashed after {duration_ms}ms")
            _set_status(db, job_id, module_key, "failed",
                        f"{type(exc).__name__}: {exc}")
            # Retry once with a short backoff — many failures are flaky
            # imports (lifetimes warnings, prophet stan) that succeed on
            # retry once the worker has them cached.
            raise self.retry(exc=exc, countdown=10)
        duration_ms = int((time.time() - t0) * 1000)

        # Persist.
        # We use the module's unique `key` (e.g. 'A01_revenue_summary') as the
        # cache row's analysis_type instead of the broad category string
        # (e.g. 'revenue') because the cache table has a UNIQUE constraint on
        # (analysis_type, upload_job_id). Eight modules return analysis_type
        # 'revenue' — sharing the key would have them overwrite each other,
        # leaving only the last-completed module's output visible.
        # The original category lives at module.analysis_type if any router
        # still wants it for grouping.
        cache_key = module.key
        analysis_type_category = module.analysis_type or "unknown"
        _upsert_result(db, job_id, cache_key, sanitize_json(result), duration_ms)
        _set_status(db, job_id, module_key, "completed")

        logger.info(f"[{module_key}] completed in {duration_ms}ms — "
                    f"category={analysis_type_category}")
        return {"status": "completed", "module_key": module_key,
                "duration_ms": duration_ms,
                "analysis_type": analysis_type_category}

    finally:
        db.close()
