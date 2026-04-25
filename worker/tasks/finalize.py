"""Stage 7 — Finalize pipeline after all analytics modules complete.

1. Flip upload_jobs.status → "completed", set completed_at.
2. Snapshot daily_kpi_snapshots from orders.
3. Trigger LLM insight generation.
"""

import os
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from celery_app import celery_app

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _snapshot_daily_kpis(session, job_id: str):
    """Aggregate orders from this job into daily_kpi_snapshots."""
    try:
        session.execute(
            text("""
                INSERT INTO daily_kpi_snapshots
                    (id, snapshot_date, total_revenue, active_customers,
                     new_customers, total_orders, avg_order_value,
                     churn_rate,
                     revenue_na, revenue_eu, revenue_apac, revenue_latam)
                SELECT
                    gen_random_uuid(),
                    CURRENT_DATE,
                    COALESCE(SUM(net_amount), 0),
                    COUNT(DISTINCT customer_id),
                    COUNT(DISTINCT customer_id) FILTER (
                        WHERE customer_id IN (
                            SELECT id FROM customers WHERE cohort_month = DATE_TRUNC('month', CURRENT_DATE)
                        )
                    ),
                    COUNT(*),
                    COALESCE(AVG(net_amount), 0),
                    0,
                    COALESCE(SUM(net_amount) FILTER (WHERE region = 'NA'), 0),
                    COALESCE(SUM(net_amount) FILTER (WHERE region = 'EU'), 0),
                    COALESCE(SUM(net_amount) FILTER (WHERE region = 'APAC'), 0),
                    COALESCE(SUM(net_amount) FILTER (WHERE region = 'LATAM'), 0)
                FROM orders
                WHERE upload_job_id = :job_id
                ON CONFLICT (snapshot_date)
                DO UPDATE SET
                    total_revenue = EXCLUDED.total_revenue,
                    active_customers = EXCLUDED.active_customers,
                    new_customers = EXCLUDED.new_customers,
                    total_orders = EXCLUDED.total_orders,
                    avg_order_value = EXCLUDED.avg_order_value,
                    revenue_na = EXCLUDED.revenue_na,
                    revenue_eu = EXCLUDED.revenue_eu,
                    revenue_apac = EXCLUDED.revenue_apac,
                    revenue_latam = EXCLUDED.revenue_latam,
                    updated_at = NOW()
            """),
            {"job_id": job_id},
        )
        session.commit()
        logger.info("Job %s: daily KPI snapshot saved.", job_id)
    except Exception as e:
        logger.warning("Job %s: KPI snapshot failed — %s", job_id, e)
        session.rollback()


@celery_app.task(bind=True, name="tasks.finalize.run_finalize")
def run_finalize(self, results, job_id: str):
    """Stage 7 callback — runs after all analytics tasks in the chord complete.

    Args:
        results: List of return values from the chord tasks (auto-injected by Celery).
        job_id: The upload job ID.
    """
    logger.info("Starting finalization for job %s", job_id)
    db = SessionLocal()

    try:
        # 1. Flip job status → completed
        db.execute(
            text("""
                UPDATE upload_jobs
                SET status = 'completed',
                    completed_at = :now,
                    updated_at = :now
                WHERE id = :job_id
            """),
            {"job_id": job_id, "now": datetime.now(timezone.utc)},
        )
        db.commit()
        logger.info("Job %s: status set to 'completed'.", job_id)

        # 2. Snapshot daily KPIs
        _snapshot_daily_kpis(db, job_id)

        # 3. Trigger LLM insight generation (best-effort, non-blocking)
        try:
            celery_app.send_task(
                "tasks.insights.run_insights",
                args=[job_id],
            )
            logger.info("Job %s: insights generation dispatched.", job_id)
        except Exception as e:
            logger.warning("Job %s: failed to dispatch insights — %s", job_id, e)

        # Log summary of analytics results
        completed = db.execute(
            text("""
                SELECT COUNT(*) FROM analytics_module_status
                WHERE upload_job_id = :job_id AND run_status = 'completed'
            """),
            {"job_id": job_id},
        ).scalar()

        failed = db.execute(
            text("""
                SELECT COUNT(*) FROM analytics_module_status
                WHERE upload_job_id = :job_id AND run_status = 'failed'
            """),
            {"job_id": job_id},
        ).scalar()

        logger.info(
            "Job %s: finalization complete — %d modules completed, %d failed.",
            job_id, completed or 0, failed or 0,
        )

        return {
            "status": "finalized",
            "job_id": job_id,
            "modules_completed": completed or 0,
            "modules_failed": failed or 0,
        }

    except Exception as e:
        logger.error("Job %s: finalization failed — %s", job_id, e, exc_info=True)
        try:
            db.execute(
                text("""
                    UPDATE upload_jobs
                    SET status = 'failed',
                        error_message = :err,
                        updated_at = NOW()
                    WHERE id = :job_id
                """),
                {"job_id": job_id, "err": f"Finalization error: {e}"},
            )
            db.commit()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=15, max_retries=2)
    finally:
        db.close()
