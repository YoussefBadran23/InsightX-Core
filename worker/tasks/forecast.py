"""Stage 6 (ML) — Revenue Forecasting Orchestrator."""
import os
import logging
import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from celery_app import celery_app
from tasks.analytics.a15_prophet_forecast import run_prophet_forecast

logger = logging.getLogger(__name__)

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

@celery_app.task(bind=True, name="tasks.forecast.run_forecast")
def run_forecast(self, job_id: str):
    """
    Orchestrates the revenue forecasting process for a specific job.
    Leverages the A15 analytics module for detailed time-series logic.
    """
    logger.info(f"Starting revenue forecast orchestration for job {job_id}")
    db = SessionLocal()
    
    try:
        # Check if the job exists and is in the correct state
        job_exists = db.execute(
            text("SELECT 1 FROM upload_jobs WHERE id = :job_id"), 
            {"job_id": job_id}
        ).scalar()
        
        if not job_exists:
            logger.error(f"Forecast failed: Job {job_id} not found.")
            return {"status": "error", "message": "Job not found"}

        # Execute the primary forecasting logic
        # Note: run_prophet_forecast handles its own DB upserts and status updates
        result = run_prophet_forecast(job_id)
        
        logger.info(f"Forecast orchestration complete for job {job_id}.")
        return {
            "status": "success", 
            "job_id": job_id, 
            "method": result.get("method", "unknown")
        }

    except Exception as e:
        logger.error(f"Forecast Orchestration failed for {job_id}: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=30, max_retries=2)
    finally:
        db.close()