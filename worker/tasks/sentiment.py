"""Stage 6 (ML) — Sentiment Analysis Orchestrator."""
import os
import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from celery_app import celery_app
from tasks.analytics.a18_sentiment_analysis import run_sentiment_analysis

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

@celery_app.task(bind=True, name="tasks.sentiment.run_sentiment")
def run_sentiment(self, job_id: str):
    """
    Analyzes customer feedback and order comments for sentiment trends.
    """
    logger.info(f"Starting sentiment orchestration for job {job_id}")
    db = SessionLocal()
    
    try:
        # Verify job state
        res = db.execute(text("SELECT status FROM upload_jobs WHERE id = :id"), {"id": job_id}).fetchone()
        if not res: return {"status": "error", "message": "Job not found"}

        # Execute classification
        # run_sentiment_analysis performs its own DB updates
        result = run_sentiment_analysis(job_id)
        
        return {"status": "success", "analyzed": result.get("total_analyzed", 0)}

    except Exception as e:
        logger.error(f"Sentiment Task failed: {e}")
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()