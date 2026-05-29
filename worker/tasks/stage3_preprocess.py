"""Stage 3 — Preprocess. Cleans CSV using confirmed mappings and saves to Parquet."""

import os
import pandas as pd
from celery import shared_task
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from db import get_db_session
from app.models.upload_job import UploadJob
# Currency-aware coercion (strips $, commas, locale junk before pd.to_numeric)
# and date coercion that handles mixed formats — both live in the analytics
# _base module so the same logic is used at preprocess time and at run time.
from tasks.analytics._base import coerce_numeric, coerce_date

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
CLEANED_DIR = os.path.join(UPLOAD_DIR, "cleaned")
os.makedirs(CLEANED_DIR, exist_ok=True)

@shared_task(name="tasks.pipeline.stage3_preprocess", bind=True)
def stage3_preprocess(self, job_id_str: str) -> str:
    """Reads raw CSV, applies confirmed mappings, coerces types, saves Parquet."""

    try:
        return _stage3_inner(job_id_str)
    except Exception as exc:
        # Ensure the job is marked as failed in the DB so the poller receives a
        # terminal status instead of waiting until the 15-minute timeout.
        try:
            with get_db_session() as db:
                job = db.query(UploadJob).filter(UploadJob.id == job_id_str).first()
                if job and job.status not in ("completed", "completed_with_errors", "failed"):
                    job.status = "failed"
                    job.error_message = str(exc)[:500]
                    db.commit()
        except Exception:
            pass
        raise


def _stage3_inner(job_id_str: str) -> str:
    """Core stage-3 logic (called by the Celery task wrapper above)."""

    with get_db_session() as db:
        job = db.query(UploadJob).filter(UploadJob.id == job_id_str).first()
        if not job:
            raise ValueError(f"Job {job_id_str} not found")

        job.status = "validating"
        db.commit()

        # IMPORTANT GOTCHA: Use "mapped_column" in SQL, not "mapped_column_name"
        query = text("""
            SELECT csv_header, mapped_column
            FROM csv_column_mappings
            WHERE upload_job_id = :job_id AND is_confirmed = true
        """)
        mappings = db.execute(query, {"job_id": job_id_str}).fetchall()
        
        rename_map_raw = {row.csv_header: row.mapped_column for row in mappings}

        # Deduplicate: when the sniff model maps multiple CSV headers to the
        # same internal column, keep only the first occurrence.  Downstream
        # PyArrow to_parquet and all analytics modules require unique column
        # names; without this guard a dirty/ambiguous CSV crashes the pipeline.
        seen_internal: set = set()
        rename_map: dict = {}
        for csv_col, internal_col in rename_map_raw.items():
            if internal_col not in seen_internal:
                seen_internal.add(internal_col)
                rename_map[csv_col] = internal_col

        if "total_amount" not in rename_map.values():
            raise ValueError("total_amount mapping is missing but required.")

        raw_path = os.path.join(UPLOAD_DIR, job.s3_key)

        # Detect encoding; fall back to latin-1 for legacy files.
        try:
            df = pd.read_csv(raw_path)
        except UnicodeDecodeError:
            df = pd.read_csv(raw_path, encoding='latin-1')

        rows_total = len(df)

        # Rename columns using the deduplicated map
        df.rename(columns=rename_map, inplace=True)

        # Keep only confirmed-and-deduplicated columns; order preserving.
        internal_cols_present = list(rename_map.values())
        df = df[[c for c in internal_cols_present if c in df.columns]].copy()

        # Coerce types — use currency-aware coercers from analytics/_base.py
        # so "$1,234.56" or "USD 1234" survive instead of becoming NaN.
        # 1. total_amount (required numeric)
        df["total_amount"] = coerce_numeric(df["total_amount"])
        df.dropna(subset=["total_amount"], inplace=True)

        # 2. Other numerics
        numeric_cols = [
            "net_amount", "cost_amount", "discount_amount", "quantity",
            "unit_price", "delivery_days", "age", "loyalty_points",
            "stock_qty", "reorder_level"
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = coerce_numeric(df[col])

        # 3. Dates — coerce_date uses format='mixed' so 2026-05-11, 5/11/2026,
        # and "May 11, 2026" all parse without falling to NaT.
        date_cols = ["order_date", "birth_date", "registration_date"]
        for col in date_cols:
            if col in df.columns:
                df[col] = coerce_date(df[col])
                if col == "order_date":
                    # order_date is required for most analytics, but we won't dropna here
                    # just keep NaT
                    pass

        # 4. Booleans — use isin() instead of map().fillna() to avoid pandas
        # 2.2 FutureWarning about object-dtype downcasting. Any value not in
        # the truthy set falls through as False, matching the previous logic.
        TRUTHY = {"true", "1", "yes", "y", "1.0", "t"}
        bool_cols = ["return_flag", "product_status"]
        for col in bool_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower().isin(TRUTHY)

        # 5. Strings
        string_cols = [
            "order_id", "customer_id", "product_id", "status", "acquisition_channel",
            "payment_method", "currency", "customer_name", "customer_email",
            "customer_phone", "customer_city", "region", "country", "country_code",
            "gender", "customer_segment", "comment_text", "product_name", "category",
            "subcategory", "brand", "product_description", "supplier"
        ]
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace("nan", None)
                # For required IDs, generate uuids if missing? No, drop if missing primary keys
                if col in ["order_id", "customer_id", "product_id"]:
                    df.dropna(subset=[col], inplace=True)

        # ── 5.5 Synthesize missing human-readable names ───────────────────────
        import hashlib
        
        def synth_name(id_val, prefix="Item", cat=None):
            if pd.isna(id_val) or id_val is None or str(id_val).lower() == "none": return None
            h = int(hashlib.sha256(str(id_val).encode('utf-8')).hexdigest()[:8], 16)
            adjs = ["Premium", "Essential", "Pro", "Elite", "Signature", "Advanced"]
            adj = adjs[h % len(adjs)]
            base = str(cat).title() if pd.notna(cat) and cat and str(cat).lower() != "none" else prefix
            return f"{adj} {base} {h % 1000}"

        if "product_id" in df.columns:
            if "product_name" not in df.columns:
                df["product_name"] = None
            
            mask = df["product_name"].isna() | (df["product_name"] == "None") | (df["product_name"] == "") | (df["product_name"].astype(str).str.len() > 25)
            if mask.any():
                df.loc[mask, "product_name"] = df.loc[mask].apply(
                    lambda row: synth_name(row["product_id"], "Product", row.get("category", None)), axis=1
                )

        if "customer_id" in df.columns:
            if "customer_name" not in df.columns:
                df["customer_name"] = None
            
            mask = df["customer_name"].isna() | (df["customer_name"] == "None") | (df["customer_name"] == "") | (df["customer_name"].astype(str).str.len() > 25)
            if mask.any():
                df.loc[mask, "customer_name"] = df.loc[mask, "customer_id"].apply(
                    lambda x: f"Customer {str(x)[:6].upper()}" if pd.notna(x) else None
                )

        # ── Detect source currency ────────────────────────────────────────────
        # If the CSV has a `currency` column with valid ISO codes, the mode (most
        # common value) becomes the upload's source currency. We only override
        # what's already stored on the job if the user did NOT explicitly choose
        # a currency at /upload/confirm time. The frontend reads this back so
        # `formatMoney(value, displayCurrency, { from: source_currency })` can
        # convert end-to-end (e.g. Olist BRL → user's preferred EGP via USD pivot).
        SUPPORTED_CCY = {
            "USD", "EUR", "GBP", "JPY", "CNY", "SAR", "AED", "EGP",
            "KWD", "QAR", "BHD", "OMR", "JOD", "TRY", "BRL",
        }
        if not job.source_currency and "currency" in df.columns:
            try:
                ccy_series = (
                    df["currency"].dropna().astype(str).str.upper().str.strip()
                )
                ccy_series = ccy_series[ccy_series.isin(SUPPORTED_CCY)]
                if not ccy_series.empty:
                    mode = ccy_series.mode()
                    if not mode.empty:
                        job.source_currency = str(mode.iloc[0])
            except Exception:
                # Detection is best-effort — never block the pipeline on it.
                pass
        # Final fallback: USD. Always have a non-null value going into stage4+.
        if not job.source_currency:
            job.source_currency = "USD"

        rows_processed = len(df)
        
        # Save to Parquet
        parquet_path = os.path.join(CLEANED_DIR, f"{job_id_str}.parquet")
        df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)
        
        # Update Job
        job.rows_total = rows_total
        job.rows_processed = rows_processed
        job.status = "inserting"
        db.commit()

        # Dispatch the next stage. We use celery.signature(...).delay() so we
        # don't have to import celery_app here (would be a circular import,
        # since celery_app.py includes this module). Stage 4 then fires the
        # chord of analytics modules, with stage 6 as the chord callback.
        from celery import signature
        signature("tasks.pipeline.stage4_upsert", args=[job_id_str]).delay()

        return job_id_str
