"""Stage 1 & 2 — CSV Ingestion & Semantic Mapping (Optimized)."""
import os
import logging
import pandas as pd
import chardet
from rapidfuzz import process, fuzz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from celery_app import celery_app
from app.models.upload_job import UploadJob
from app.models.csv_column_mapping import CsvColumnMapping

logger = logging.getLogger(__name__)

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

# Fuzzy match sensitivity (0.0-1.0)
FUZZY_THRESHOLD = 0.75

# Standard InsightX Schema Definitions
STANDARD_COLUMNS = {
    "order_id": {"table": "orders", "column": "id", "aliases": ["order", "invoice", "transaction_id"]},
    "customer_id": {"table": "orders", "column": "customer_id", "aliases": ["client", "user_id", "buyer"]},
    "order_date": {"table": "orders", "column": "created_at", "aliases": ["date", "timestamp", "purchase_time"]},
    "total_amount": {"table": "orders", "column": "total_amount", "aliases": ["amount", "revenue", "price", "total"]},
    "product_id": {"table": "order_items", "column": "product_id", "aliases": ["sku", "item_id", "product_code"]},
    "quantity": {"table": "order_items", "column": "quantity", "aliases": ["qty", "count", "number_of_items"]},
    "unit_price": {"table": "order_items", "column": "unit_price", "aliases": ["item_price", "cost_per_unit"]},
}

# Pre-flatten aliases for faster lookup
MATCH_POOL = {}
for key, data in STANDARD_COLUMNS.items():
    MATCH_POOL[key] = key
    for alias in data["aliases"]:
        MATCH_POOL[alias] = key

@celery_app.task(bind=True, name="tasks.csv.process_csv")
def process_csv(self, job_id: str):
    """
    Analyzes CSV structure, maps headers to internal schema, and updates job status.
    """
    db = SessionLocal()
    try:
        job = db.query(UploadJob).filter(UploadJob.id == job_id).first()
        if not job:
            return {"status": "error", "message": "Job not found"}

        job.status = "mapping"
        db.commit()

        file_path = os.path.join("/app/uploads", job.s3_key)
        if not os.path.exists(file_path):
            job.status = "failed"
            job.error_message = "File missing on disk"
            db.commit()
            return {"status": "failed"}

        # 1. Detect File Encoding (prevents crash on non-UTF8 files)
        with open(file_path, "rb") as f:
            raw_sample = f.read(65536)
        encoding = chardet.detect(raw_sample).get("encoding") or "utf-8"

        # 2. Extract Headers (Fast read - only 5 rows)
        df_sample = pd.read_csv(file_path, nrows=5, encoding=encoding, on_bad_lines="skip")
        headers = df_sample.columns.tolist()

        # 3. Perform Semantic Mapping
        mappings = []
        for header in headers:
            # Match current header against our pool of known names/aliases
            res = process.extractOne(header.lower().strip(), MATCH_POOL.keys(), scorer=fuzz.WRatio)
            
            if res and (res[1] / 100.0) >= FUZZY_THRESHOLD:
                std_key = MATCH_POOL[res[0]]
                info = STANDARD_COLUMNS[std_key]
                
                mapping = CsvColumnMapping(
                    upload_job_id=job.id,
                    csv_header=header,
                    mapped_table=info["table"],
                    mapped_column_name=info["column"],
                    match_score=float(res[1]) / 100.0,
                    is_confirmed=(res[1] >= 85) # Auto-confirm high confidence matches
                )
                mappings.append(mapping)

        # 4. Save and Advance Pipeline
        db.bulk_save_objects(mappings)
        job.status = "mapping_complete"
        db.commit()

        # Dispatch Next Stage: Preprocessing
        celery_app.send_task("tasks.preprocess.run_preprocessing", args=[job_id])
        return {"status": "success", "mapped_cols": len(mappings)}

    except Exception as e:
        db.rollback()
        logger.error(f"Mapping Failed for {job_id}: {e}")
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
        raise self.retry(exc=e, countdown=5)
    finally:
        db.close()