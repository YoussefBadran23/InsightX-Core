"""Stage 3 — Data Validation & Type Coercion (Optimized)."""
import os
import logging
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from celery_app import celery_app
from analytics_registry import check_eligibility

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

UPLOAD_DIR = "/app/uploads"

@celery_app.task(bind=True, name="tasks.preprocess.run_preprocessing")
def run_preprocessing(self, job_id: str):
    """
    Loads raw CSV, applies semantic mapping, coerces types, and saves as optimized Parquet.
    """
    db = SessionLocal()
    try:
        # 1. Load Job & Mappings
        job = db.execute(text("SELECT s3_key, user_id FROM upload_jobs WHERE id = :id"), {"id": job_id}).fetchone()
        if not job: return {"status": "error"}

        mappings = db.execute(text("""
            SELECT csv_header, mapped_column_name FROM csv_column_mapping 
            WHERE upload_job_id = :id AND is_confirmed = True
        """), {"id": job_id}).fetchall()
        
        rename_map = {row[0]: row[1] for row in mappings}
        
        # 2. Read Full Data (Memory Optimized)
        file_path = os.path.join(UPLOAD_DIR, job.s3_key)
        df = pd.read_csv(file_path, low_memory=False, on_bad_lines='skip', encoding_errors='replace')
        
        # 3. Rename and Prune
        df = df[list(rename_map.keys())].rename(columns=rename_map)

        # 4. Vectorized Coercion (Speed Optimization)
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        
        numeric_cols = ["total_amount", "net_amount", "discount_amount", "quantity", "unit_price", "delivery_days"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # 5. Data Quality Scrub
        df = df.dropna(subset=["total_amount"]) # Require revenue to be useful
        
        # 6. Save Cleaned Parquet (Storage Optimization)
        os.makedirs(f"{UPLOAD_DIR}/cleaned", exist_ok=True)
        parquet_path = f"{UPLOAD_DIR}/cleaned/{job_id}_cleaned.parquet"
        df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)

        # 7. Check Module Eligibility
        eligibility = check_eligibility(set(df.columns))
        for key, info in eligibility.items():
            db.execute(text("""
                INSERT INTO analytics_module_status (id, upload_job_id, module_key, can_run, run_status)
                VALUES (gen_random_uuid(), :jid, :key, :can, :stat)
            """), {"jid": job_id, "key": key, "can": info["can_run"], "stat": "pending" if info["can_run"] else "skipped"})

        db.execute(text("UPDATE upload_jobs SET status='validated', rows_processed=:r WHERE id=:id"), 
                   {"id": job_id, "r": len(df)})
        db.commit()

        # Advance to Upsert
        celery_app.send_task("tasks.upsert.run_upserts", args=[job_id])
        return {"status": "success", "rows": len(df)}

    except Exception as e:
        db.rollback()
        logger.error(f"Preprocessing failed: {e}")
        raise self.retry(exc=e, countdown=15)
    finally:
        db.close()