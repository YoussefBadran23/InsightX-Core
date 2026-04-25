"""Phase 3 — Step 9: Auto-Pipeline Stage 3 — Validation & Coercion.

Reads the full CSV using the column mappings created in Stage 2,
type-casts every column to the correct Python/DB type, flags invalid
rows, and writes a cleaned Parquet file for Stage 4 (upserts).

Flow:
  csv.py (Stage 1-2: mapping)
    → preprocess.py (Stage 3: validation & coercion)  ← THIS FILE
      → upsert.py (Stage 4-5: entity inserts)
"""

import os
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from celery_app import celery_app
from app.models.upload_job import UploadJob
from app.models.csv_column_mapping import CsvColumnMapping
from app.models.analytics_module_status import AnalyticsModuleStatus
from analytics_registry import check_eligibility, MODULES

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

UPLOAD_DIR = "/app/uploads"
CLEANED_DIR = "/app/uploads/cleaned"
os.makedirs(CLEANED_DIR, exist_ok=True)


# ── Column coercion helpers ──────────────────────────────────────────────────

def _coerce_date(series: pd.Series) -> pd.Series:
    """Parse a column to datetime; unparseable values become NaT."""
    return pd.to_datetime(series, errors="coerce", dayfirst=False)


def _coerce_numeric(series: pd.Series) -> pd.Series:
    """Parse a column to float; unparseable values become NaN."""
    return pd.to_numeric(series, errors="coerce")


def _coerce_integer(series: pd.Series) -> pd.Series:
    """Parse a column to integer (via float for NaN handling)."""
    return pd.to_numeric(series, errors="coerce").round(0)


def _coerce_string(series: pd.Series) -> pd.Series:
    """Normalize strings: strip whitespace, collapse empties to None."""
    s = series.astype(str).str.strip()
    s = s.replace({"": None, "nan": None, "None": None, "NaN": None, "null": None})
    return s


def _coerce_boolean(series: pd.Series) -> pd.Series:
    """Parse boolean-like values (yes/no/true/false/1/0)."""
    mapping = {
        "true": True, "yes": True, "1": True, "t": True, "y": True,
        "false": False, "no": False, "0": False, "f": False, "n": False,
    }
    return series.astype(str).str.strip().str.lower().map(mapping)


# Map target DB columns to their expected type for coercion
_COLUMN_TYPES: dict[str, str] = {
    # orders table
    "id": "string",              # external order ID
    "customer_id": "string",     # external customer ID
    "created_at": "date",        # order_date
    "total_amount": "numeric",
    "discount_amount": "numeric",
    "net_amount": "numeric",
    "cost_amount": "numeric",
    "status": "string",
    "region": "string",
    "currency": "string",
    "payment_method": "string",
    "acquisition_channel": "string",
    "return_flag": "boolean",
    "delivery_days": "integer",
    "comment_text": "string",
    # order_items table
    "product_id": "string",
    "quantity": "integer",
    "unit_price": "numeric",
    # customers (passthrough — mainly for enriched CSVs)
    "email": "string",
    "full_name": "string",
    "country": "string",
    "country_code": "string",
    # products (passthrough)
    "name": "string",
    "category": "string",
    "sku": "string",
    "cost_price": "numeric",
}


_COERCERS = {
    "string": _coerce_string,
    "date": _coerce_date,
    "numeric": _coerce_numeric,
    "integer": _coerce_integer,
    "boolean": _coerce_boolean,
}


# ── Main task ─────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="tasks.preprocess.run_preprocessing")
def run_preprocessing(self, job_id: str):
    """
    Stage 3: Validate & coerce CSV data using the mappings from Stage 2.

    1. Load confirmed column mappings from DB.
    2. Read full CSV using detected encoding.
    3. Rename CSV columns to standard DB column names.
    4. Apply type coercion per column.
    5. Flag and count invalid rows.
    6. Save cleaned data as Parquet for fast downstream reads.
    7. Update UploadJob with row counts and status.
    """
    logger.info("Starting validation & coercion for job %s", job_id)
    db = SessionLocal()

    try:
        # ── 1. Load job & mappings ────────────────────────────────────────
        job = db.query(UploadJob).filter(UploadJob.id == job_id).first()
        if not job:
            logger.error("Job %s not found.", job_id)
            return {"status": "error", "message": "Job not found"}

        job.status = "validating"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        # Get all confirmed mappings from Stage 2
        mappings = (
            db.query(CsvColumnMapping)
            .filter(
                CsvColumnMapping.upload_job_id == job.id,
                CsvColumnMapping.is_confirmed == True,  # noqa: E712
            )
            .all()
        )

        if not mappings:
            job.status = "failed"
            job.error_message = "No confirmed column mappings found. Cannot proceed."
            db.commit()
            logger.error("Job %s has no confirmed mappings.", job_id)
            return {"status": "failed", "message": "No confirmed mappings"}

        # Build rename dict: csv_header → mapped DB column name
        rename_map: dict[str, str] = {}
        table_map: dict[str, str] = {}  # db_column → target table
        for m in mappings:
            rename_map[m.csv_header] = m.mapped_column_name
            table_map[m.mapped_column_name] = m.mapped_table

        logger.info(
            "Job %s: %d confirmed mappings — %s",
            job_id, len(mappings), rename_map,
        )

        # ── 2. Read full CSV ──────────────────────────────────────────────
        file_path = os.path.join(UPLOAD_DIR, job.s3_key)
        if not os.path.exists(file_path):
            job.status = "failed"
            job.error_message = "File not found on disk."
            db.commit()
            return {"status": "failed", "message": "File not found"}

        # Detect encoding
        try:
            import chardet
            with open(file_path, "rb") as f:
                raw_sample = f.read(65536)
            detected = chardet.detect(raw_sample)
            encoding = detected.get("encoding") or "utf-8"
            if encoding.lower() == "ascii":
                encoding = "latin1"
        except ImportError:
            encoding = "utf-8"

        logger.info("Job %s: reading CSV with encoding=%s", job_id, encoding)

        try:
            df = pd.read_csv(
                file_path,
                encoding=encoding,
                on_bad_lines="skip",
                low_memory=False,
                encoding_errors="replace",
            )
        except Exception as parse_err:
            job.status = "failed"
            job.error_message = f"CSV parse error: {parse_err}"
            db.commit()
            logger.error("Job %s: CSV parse failed — %s", job_id, parse_err)
            return {"status": "failed", "message": str(parse_err)}

        total_rows = len(df)
        job.rows_total = total_rows
        db.commit()
        logger.info("Job %s: read %d rows from CSV.", job_id, total_rows)

        if total_rows == 0:
            job.status = "failed"
            job.error_message = "CSV contains no data rows."
            db.commit()
            return {"status": "failed", "message": "Empty CSV"}

        # ── 3. Rename columns ─────────────────────────────────────────────
        # Only keep columns that have a confirmed mapping
        mapped_headers = set(rename_map.keys())
        available_headers = set(df.columns)
        usable = mapped_headers & available_headers
        missing = mapped_headers - available_headers

        if missing:
            logger.warning(
                "Job %s: mapped headers not found in CSV: %s", job_id, missing
            )

        # Filter to only mapped columns, then rename
        df = df[[h for h in df.columns if h in usable]].copy()
        df.rename(columns=rename_map, inplace=True)
        
        # If multiple original headers mapped to the same target DB column, drop duplicates
        if df.columns.duplicated().any():
            logger.warning("Job %s: duplicate target columns found after mapping, keeping first.", job_id)
            df = df.loc[:, ~df.columns.duplicated()].copy()

        # ── 4. Type coercion ──────────────────────────────────────────────
        errors_per_row = pd.Series(0, index=df.index)

        for col in df.columns:
            expected_type = _COLUMN_TYPES.get(col)
            if not expected_type:
                logger.info("Job %s: column '%s' has no type rule — keeping as-is.", job_id, col)
                continue

            coercer = _COERCERS.get(expected_type)
            if not coercer:
                continue

            before_nulls = df[col].isna().sum()
            df[col] = coercer(df[col])
            after_nulls = df[col].isna().sum()
            new_nulls = after_nulls - before_nulls

            if new_nulls > 0:
                logger.warning(
                    "Job %s: column '%s' — %d values failed %s coercion",
                    job_id, col, new_nulls, expected_type,
                )
                # Track which rows got new NaNs from coercion
                errors_per_row += df[col].isna().astype(int)

        # ── 5. Flag invalid rows ──────────────────────────────────────────
        # Required columns: at least order_id or a date + amount to be useful
        required_cols = {"total_amount"}  # must have at least amount
        missing_required = required_cols - set(df.columns)

        if missing_required:
            logger.warning(
                "Job %s: required columns missing after mapping: %s — proceeding anyway",
                job_id, missing_required,
            )

        # Drop rows where ALL mapped values are NaN (completely empty)
        empty_mask = df.isna().all(axis=1)
        rows_empty = empty_mask.sum()
        if rows_empty > 0:
            df = df[~empty_mask].copy()
            logger.info("Job %s: dropped %d completely empty rows.", job_id, rows_empty)

        # Drop rows where critical numeric columns are NaN (if they exist)
        critical_numeric = [c for c in ("total_amount", "quantity", "unit_price") if c in df.columns]
        if critical_numeric:
            bad_rows_mask = df[critical_numeric].isna().any(axis=1)
            rows_failed = int(bad_rows_mask.sum())
            df_clean = df[~bad_rows_mask].copy()
        else:
            rows_failed = 0
            df_clean = df.copy()

        rows_valid = len(df_clean)

        logger.info(
            "Job %s: validation complete — %d valid, %d failed, %d empty dropped",
            job_id, rows_valid, rows_failed, rows_empty,
        )

        # ── 6. Derive computed columns ────────────────────────────────────
        # net_amount = total_amount - discount_amount
        if "total_amount" in df_clean.columns:
            if "discount_amount" not in df_clean.columns:
                df_clean["discount_amount"] = 0.0
            df_clean["discount_amount"] = df_clean["discount_amount"].fillna(0.0)
            df_clean["net_amount"] = df_clean["total_amount"] - df_clean["discount_amount"]

        # line_total = quantity * unit_price
        if "quantity" in df_clean.columns and "unit_price" in df_clean.columns:
            df_clean["line_total"] = df_clean["quantity"] * df_clean["unit_price"]

        # Default status to "completed" if not present
        if "status" not in df_clean.columns:
            df_clean["status"] = "completed"

        # Default currency to "USD" if not present
        if "currency" not in df_clean.columns:
            df_clean["currency"] = "USD"

        # Default region to "NA" if not present
        if "region" not in df_clean.columns:
            df_clean["region"] = "NA"

        # ── 7. Save cleaned data as Parquet ───────────────────────────────
        parquet_filename = f"{job_id}_cleaned.parquet"
        parquet_path = os.path.join(CLEANED_DIR, parquet_filename)

        df_clean.to_parquet(parquet_path, index=False, engine="pyarrow")
        logger.info("Job %s: saved cleaned data to %s (%d rows)", job_id, parquet_path, rows_valid)

        # ── 8. Compute analytics module eligibility ─────────────────────
        available_db_cols = set(df_clean.columns)
        eligibility = check_eligibility(available_db_cols)

        runnable = 0
        blocked = 0
        for key, info in eligibility.items():
            mod = info["module"]
            status_row = AnalyticsModuleStatus(
                upload_job_id=job.id,
                module_key=key,
                module_name=mod.name,
                module_name_ar=mod.name_ar,
                description=mod.description,
                can_run=info["can_run"],
                queue=mod.queue,
                missing_required_columns=sorted(info["missing_required"]) if info["missing_required"] else None,
                missing_optional_columns=sorted(info["missing_optional"]) if info["missing_optional"] else None,
                run_status="pending" if info["can_run"] else "skipped",
            )
            db.add(status_row)

            if info["can_run"]:
                runnable += 1
            else:
                blocked += 1
                logger.warning(
                    "Job %s: module %s BLOCKED — missing: %s",
                    job_id, key, info["missing_required"],
                )

        logger.info(
            "Job %s: %d/%d modules can run, %d blocked.",
            job_id, runnable, len(MODULES), blocked,
        )

        # ── 9. Update job status ──────────────────────────────────────────
        job.rows_processed = rows_valid
        job.rows_failed = rows_failed
        job.status = "validated"
        db.commit()

        logger.info("Job %s: Stage 3 (validation) complete.", job_id)

        # Chain → Stage 4-5: Entity & Dimension Upserts
        celery_app.send_task("tasks.upsert.run_upserts", args=[job_id])
        logger.info("Dispatched upsert task for job %s.", job_id)

        return {
            "status": "success",
            "rows_total": total_rows,
            "rows_valid": rows_valid,
            "rows_failed": rows_failed,
            "modules_runnable": runnable,
            "modules_blocked": blocked,
            "parquet_path": parquet_path,
        }

    except Exception as e:
        logger.error("Job %s: preprocessing failed — %s", job_id, e, exc_info=True)
        try:
            job.status = "failed"
            job.error_message = f"Preprocessing error: {e}"
            db.commit()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=15, max_retries=3)
    finally:
        db.close()
