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
        
        rename_map = {row.csv_header: row.mapped_column for row in mappings}
        
        if "total_amount" not in rename_map.values():
            raise ValueError("total_amount mapping is missing but required.")

        raw_path = os.path.join(UPLOAD_DIR, job.s3_key)
        
        # We need to detect encoding. Let's use utf-8 or fallbacks
        try:
            df = pd.read_csv(raw_path)
        except UnicodeDecodeError:
            df = pd.read_csv(raw_path, encoding='latin-1')
            
        rows_total = len(df)
        
        # Rename columns
        df.rename(columns=rename_map, inplace=True)
        
        # Drop columns we don't care about (not in our schema)
        internal_cols_present = list(rename_map.values())
        df = df[internal_cols_present].copy()

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
