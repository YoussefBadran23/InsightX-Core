"""Stage 4 & 5 — High-Speed Database Upserts (Optimized)."""
import os
import uuid
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from celery import chord, signature
from celery_app import celery_app

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL, pool_size=20)
SessionLocal = sessionmaker(bind=engine)

@celery_app.task(bind=True, name="tasks.upsert.run_upserts")
def run_upserts(self, job_id: str):
    """
    Reads cleaned data and performs bulk inserts for Customers, Products, and Orders.
    Uses Postgres 'ON CONFLICT' for O(1) upsert performance.
    """
    db = SessionLocal()
    try:
        # 1. Load Data
        path = f"/app/uploads/cleaned/{job_id}_cleaned.parquet"
        df = pd.read_parquet(path)
        user_id = db.execute(text("SELECT user_id FROM upload_jobs WHERE id = :id"), {"id": job_id}).scalar()

        # 2. Bulk Upsert Customers
        if "customer_id" in df.columns:
            customers = df[["customer_id"]].drop_duplicates().rename(columns={"customer_id": "ext_id"})
            cust_batch = [{"uid": user_id, "eid": str(r.ext_id)} for r in customers.itertuples()]
            db.execute(text("""
                INSERT INTO customers (id, user_id, external_id, email, is_active, created_at, updated_at)
                VALUES (gen_random_uuid(), :uid, :eid, :eid || '@imported.insightx', True, NOW(), NOW())
                ON CONFLICT (external_id) DO NOTHING
            """), cust_batch)

        # 3. Bulk Upsert Products
        if "product_id" in df.columns:
            products = df[["product_id"]].drop_duplicates()
            prod_batch = [{"uid": user_id, "sku": str(r.product_id)[:20]} for r in products.itertuples()]
            db.execute(text("""
                INSERT INTO products (id, user_id, sku, name, is_active, created_at, updated_at)
                VALUES (gen_random_uuid(), :uid, :sku, :sku, True, NOW(), NOW())
                ON CONFLICT (sku) DO NOTHING
            """), prod_batch)

        db.commit()

        # 4. Final Analysis Chord (Parallel Execution of 22 modules)
        eligible_tasks = db.execute(text("""
            SELECT module_key FROM analytics_module_status 
            WHERE upload_job_id = :jid AND can_run = True
        """), {"jid": job_id}).fetchall()
        
        task_list = [signature(f"tasks.analytics.{t[0]}", args=[job_id]) for t in eligible_tasks]
        
        if task_list:
            # Chord: Run all analytics -> when done -> run Finalize
            callback = signature("tasks.finalize.run_finalize", kwargs={"job_id": job_id})
            chord(task_list)(callback)
        else:
            celery_app.send_task("tasks.finalize.run_finalize", args=[[], job_id])

        return {"status": "upsert_complete", "tasks_dispatched": len(task_list)}

    except Exception as e:
        db.rollback()
        logger.error(f"Upsert critical failure: {e}")
        raise self.retry(exc=e, countdown=20)
    finally:
        db.close()