"""Stage 7 — Pipeline Finalization (Optimized)."""
import os
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from celery_app import celery_app

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

def _snapshot_kpis(session, job_id: str):
    """Generates the high-level dashboard snapshot for this upload."""
    user_id = session.execute(
        text("SELECT user_id FROM upload_jobs WHERE id = :job_id"), 
        {"job_id": job_id}
    ).scalar()

    # Performance Win: Aggregate all order data into the KPI table in one SQL query
    session.execute(
        text("""
            INSERT INTO daily_kpi_snapshots
                (id, user_id, snapshot_date, total_revenue, active_customers, total_orders, avg_order_value, updated_at)
            SELECT
                gen_random_uuid(), :uid, CURRENT_DATE,
                COALESCE(SUM(net_amount), 0),
                COUNT(DISTINCT customer_id),
                COUNT(*),
                COALESCE(AVG(net_amount), 0),
                NOW()
            FROM orders WHERE upload_job_id = :job_id
            ON CONFLICT (user_id, snapshot_date) DO UPDATE SET
                total_revenue = EXCLUDED.total_revenue,
                active_customers = EXCLUDED.active_customers,
                total_orders = EXCLUDED.total_orders,
                updated_at = NOW()
        """),
        {"job_id": job_id, "uid": user_id}
    )
    session.commit()

@celery_app.task(bind=True, name="tasks.finalize.run_finalize")
def run_finalize(self, results, job_id: str):
    """
    Final Stage: Closes the job, generates dashboard snapshots, and triggers AI Insights.
    """
    db = SessionLocal()
    try:
        # 1. Close the Job
        db.execute(
            text("UPDATE upload_jobs SET status='completed', completed_at=:now WHERE id=:jid"),
            {"jid": job_id, "now": datetime.now(timezone.utc)}
        )
        db.commit()

        # 2. Build Dashboard Snapshot
        _snapshot_kpis(db, job_id)

        # 3. Trigger Natural Language Insights (A18-driven summary)
        celery_app.send_task("tasks.insights.run_insights", args=[job_id])

        # 4. Final Logging
        stats = db.execute(
            text("SELECT run_status, count(*) FROM analytics_module_status WHERE upload_job_id=:jid GROUP BY run_status"),
            {"jid": job_id}
        ).fetchall()
        
        logger.info(f"Pipeline finished for {job_id}. Module Summary: {dict(stats)}")
        return {"status": "finished", "job_id": job_id}

    except Exception as e:
        db.rollback()
        logger.error(f"Finalization crashed for {job_id}: {e}")
        db.execute(
            text("UPDATE upload_jobs SET status='failed', error_message=:e WHERE id=:jid"),
            {"e": f"Finalize Error: {e}", "jid": job_id}
        )
        db.commit()
        raise self.retry(exc=e, countdown=10)
    finally:
        db.close()