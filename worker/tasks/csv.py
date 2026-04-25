"""Step 8 (Phase 2): Auto-Pipeline Stage 1 & 2 — CSV Ingestion & Mapping."""

import os
import logging
import pandas as pd
from rapidfuzz import process, fuzz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from celery_app import celery_app
from app.models.upload_job import UploadJob
from app.models.csv_column_mapping import CsvColumnMapping

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Configurable fuzzy-match threshold (0.0–1.0). Headers below this are skipped.
FUZZY_THRESHOLD = float(os.getenv("CSV_FUZZY_THRESHOLD", "0.75"))

# Expected core schema fields
STANDARD_COLUMNS = {
    "order_id": {"table": "orders", "column": "id", "aliases": ["order", "order id", "invoice", "transaction"]},
    "customer_id": {"table": "orders", "column": "customer_id", "aliases": ["client", "customer", "user", "buyer id"]},
    "order_date": {"table": "orders", "column": "created_at", "aliases": ["date", "created", "timestamp", "purchase date"]},
    "amount": {"table": "orders", "column": "total_amount", "aliases": ["total", "price", "sale", "revenue", "amount"]},
    "product_id": {"table": "order_items", "column": "product_id", "aliases": ["item", "product", "sku", "article"]},
    "quantity": {"table": "order_items", "column": "quantity", "aliases": ["qty", "count", "amount bought"]},
    "price": {"table": "order_items", "column": "unit_price", "aliases": ["unit price", "cost", "item price"]},
}

# Flatten aliases for rapidfuzz matching
TARGET_CHOICES: dict[str, str] = {}
for std_key, data in STANDARD_COLUMNS.items():
    TARGET_CHOICES[std_key] = std_key
    for alias in data["aliases"]:
        TARGET_CHOICES[alias] = std_key


@celery_app.task(bind=True, name="tasks.csv.process_csv")
def process_csv(self, job_id: str):
    """
    Reads the top 5 rows of a CSV to grab headers, maps them semantically
    using RapidFuzz, and stores the mapping in the DB.
    """
    logger.info("Starting CSV auto-mapping for job %s", job_id)
    db = SessionLocal()

    try:
        job = db.query(UploadJob).filter(UploadJob.id == job_id).first()
        if not job:
            logger.error("Job %s not found.", job_id)
            return {"status": "error", "message": "Job not found"}

        job.status = "mapping"
        db.commit()

        file_path = os.path.join("/app/uploads", job.s3_key)

        if not os.path.exists(file_path):
            job.status = "failed"
            job.error_message = "File not found on disk."
            db.commit()
            return {"status": "failed", "message": "File not found"}

        # Detect encoding then read headers
        try:
            import chardet
            with open(file_path, "rb") as f:
                raw = f.read(65536)  # sample first 64 KB
            detected = chardet.detect(raw)
            encoding = detected.get("encoding") or "utf-8"
            if encoding.lower() == "ascii":
                encoding = "latin1" # Fallback to latin1 if ascii is detected to avoid crashes later
        except ImportError:
            encoding = "utf-8"

        try:
            df = pd.read_csv(file_path, nrows=5, encoding=encoding, on_bad_lines="skip", encoding_errors="replace")
        except Exception as parse_err:
            job.status = "failed"
            job.error_message = f"Could not parse CSV: {parse_err}"
            db.commit()
            logger.error("CSV parse error for job %s: %s", job_id, parse_err)
            return {"status": "failed", "message": str(parse_err)}

        headers = df.columns.tolist()

        mappings = []
        for header in headers:
            match = process.extractOne(
                header.lower().strip(),
                TARGET_CHOICES.keys(),
                scorer=fuzz.WRatio,
            )

            if match:
                matched_alias, score, _ = match
                normalized_score = float(score) / 100.0

                if normalized_score < FUZZY_THRESHOLD:
                    logger.warning(
                        "Job %s: header '%s' matched '%s' with score %.2f (below threshold %.2f) — skipping",
                        job_id, header, matched_alias, normalized_score, FUZZY_THRESHOLD,
                    )
                    continue

                std_key = TARGET_CHOICES[matched_alias]
                target_info = STANDARD_COLUMNS[std_key]
                is_confirmed = normalized_score >= 0.85

                mapping = CsvColumnMapping(
                    upload_job_id=job.id,
                    csv_header=header,
                    mapped_table=target_info["table"],
                    mapped_column_name=target_info["column"],
                    match_score=normalized_score,
                    match_method="fuzzy",
                    is_confirmed=is_confirmed,
                )
                mappings.append(mapping)
            else:
                logger.warning("Job %s: header '%s' had no fuzzy match — skipping", job_id, header)

        db.bulk_save_objects(mappings)
        job.status = "mapping_complete"
        db.commit()

        logger.info("Auto-mapped %d columns for job %s.", len(mappings), job_id)

        # Chain → Stage 3: Validation & Coercion
        celery_app.send_task("tasks.preprocess.run_preprocessing", args=[job_id])
        logger.info("Dispatched preprocessing task for job %s.", job_id)

        return {"status": "success", "mapped": len(mappings)}

    except Exception as e:
        logger.error("Failed CSV processing for job %s: %s", job_id, e)
        try:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=10, max_retries=3)
    finally:
        db.close()
