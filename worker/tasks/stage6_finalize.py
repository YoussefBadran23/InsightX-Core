"""Stage 6 — Finalize. Closes the job, snapshots dashboard KPIs, and writes
analytics-derived segments back to the denormalized columns on `customers`
and `products` so the dashboard list pages can render them without joining
through `analysis_results_cache` on every request.

Called as the chord callback after every dispatched analytics module
finishes. Receives the chord's per-child results as the first argument
(we don't actually inspect them — we read final status from
`analytics_module_status` instead, which is more reliable than the chord
result list because failed/retried tasks are accurately reflected there).

Responsibilities:
1. Compute pass/fail counts → set job.status to completed or completed_with_errors.
2. Snapshot today's KPIs into `daily_kpi_snapshots` from the orders table.
   This feeds the dashboard home page (KPI cards + regional revenue bars).
3. Denormalize A02_rfm_scoring → customers.rfm_segment / rfm_score / ai_segment.
4. Denormalize A07_abc_classification → products.abc_tier.
"""

from __future__ import annotations

import logging
from celery import shared_task
from sqlalchemy import text

from db import get_db_session
from app.models.upload_job import UploadJob
from app.models.analytics_module_status import AnalyticsModuleStatus

logger = logging.getLogger(__name__)


_RFM_TO_AI_SEGMENT = {
    "Champions": "vip_champion",
    "Loyal Customers": "loyalist",
    "Potential Loyalists": "loyalist",
    "New Customers": "new_potential",
    "Promising": "new_potential",
    "Need Attention": "loyalist",
    "About to Sleep": "at_risk",
    "At Risk": "at_risk",
    "Cannot Lose Them": "at_risk",
    "Hibernating": "at_risk",
    "Lost": "at_risk",
}


def _denormalize_rfm(db, user_id, job_id: str) -> int:
    """Read A02_rfm_scoring cache, write segments back onto customer rows.

    Returns the number of customer rows updated. Safe to call even if A02
    didn't run — returns 0 and leaves rows untouched.
    """
    row = db.execute(
        text("""
            SELECT result_json FROM analysis_results_cache
             WHERE upload_job_id = :jid AND analysis_type = 'A02_rfm_scoring'
             LIMIT 1
        """),
        {"jid": job_id},
    ).fetchone()
    if not row or not row[0]:
        return 0

    top_customers = (row[0] or {}).get("top_customers") or []
    if not top_customers:
        return 0

    updates = []
    for c in top_customers:
        cid = c.get("customer_id")
        seg = c.get("segment")
        rfm = c.get("RFM_score")
        if not cid:
            continue
        updates.append({
            "ext": str(cid),
            "uid": str(user_id),
            "seg": str(seg) if seg else None,
            "ai": _RFM_TO_AI_SEGMENT.get(seg, "undetermined") if seg else None,
            "rfm": str(rfm) if rfm else None,
        })

    if not updates:
        return 0

    db.execute(
        text("""
            UPDATE customers SET
                rfm_segment = :seg,
                ai_segment  = :ai,
                rfm_score   = :rfm
              WHERE external_id = :ext AND user_id = CAST(:uid AS uuid)
        """),
        updates,
    )
    db.commit()
    return len(updates)


def _denormalize_abc(db, user_id, job_id: str) -> int:
    """Read A07_abc_classification cache, write abc_tier onto product rows."""
    row = db.execute(
        text("""
            SELECT result_json FROM analysis_results_cache
             WHERE upload_job_id = :jid AND analysis_type = 'A07_abc_classification'
             LIMIT 1
        """),
        {"jid": job_id},
    ).fetchone()
    if not row or not row[0]:
        return 0

    products = (row[0] or {}).get("products") or []
    if not products:
        return 0

    updates = []
    for p in products:
        pid = p.get("product_id")
        tier = p.get("tier")
        if not pid or not tier:
            continue
        # Product.sku is varchar(20) — same truncation rule as stage4 insert.
        updates.append({
            "sku": str(pid)[:20],
            "uid": str(user_id),
            "tier": str(tier)[:1],
        })

    if not updates:
        return 0

    db.execute(
        text("""
            UPDATE products SET abc_tier = :tier
              WHERE sku = :sku AND user_id = CAST(:uid AS uuid)
        """),
        updates,
    )
    db.commit()
    return len(updates)


def _snapshot_kpis(db, user_id, job_id: str) -> None:
    """Compute today's KPI snapshot from orders for this user.

    Uses COALESCE(net_amount, total_amount) so CSVs without a net_amount
    column don't silently snapshot zero revenue. Regional revenue uses CASE
    WHEN matching against region values produced by the dataset adapters
    (NA / EU / APAC / LATAM / MENA).
    """
    db.execute(
        text("""
            INSERT INTO daily_kpi_snapshots (
                id, user_id, snapshot_date,
                total_revenue, active_customers, new_customers,
                total_orders, churn_rate, avg_order_value,
                revenue_na, revenue_eu, revenue_apac, revenue_latam,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(), :uid, CURRENT_DATE,
                COALESCE(SUM(COALESCE(o.net_amount, o.total_amount)), 0),
                COUNT(DISTINCT o.customer_id),
                COUNT(DISTINCT o.customer_id) FILTER (
                    WHERE c.first_purchase_date >= CURRENT_DATE - INTERVAL '30 days'
                ),
                COUNT(*),
                0,  -- churn_rate computed by A20 (separate module); leave 0 here
                COALESCE(AVG(COALESCE(o.net_amount, o.total_amount)), 0),
                COALESCE(SUM(CASE WHEN c.region = 'NA'    THEN COALESCE(o.net_amount, o.total_amount) END), 0),
                COALESCE(SUM(CASE WHEN c.region = 'EU'    THEN COALESCE(o.net_amount, o.total_amount) END), 0),
                COALESCE(SUM(CASE WHEN c.region = 'APAC'  THEN COALESCE(o.net_amount, o.total_amount) END), 0),
                COALESCE(SUM(CASE WHEN c.region = 'LATAM' THEN COALESCE(o.net_amount, o.total_amount) END), 0),
                NOW(), NOW()
            FROM orders o
            LEFT JOIN customers c ON c.id = o.customer_id
            WHERE o.user_id = :uid
              AND o.upload_job_id = :jid
            ON CONFLICT (user_id, snapshot_date) DO UPDATE SET
                total_revenue    = EXCLUDED.total_revenue,
                active_customers = EXCLUDED.active_customers,
                new_customers    = EXCLUDED.new_customers,
                total_orders     = EXCLUDED.total_orders,
                avg_order_value  = EXCLUDED.avg_order_value,
                revenue_na       = EXCLUDED.revenue_na,
                revenue_eu       = EXCLUDED.revenue_eu,
                revenue_apac     = EXCLUDED.revenue_apac,
                revenue_latam    = EXCLUDED.revenue_latam,
                updated_at       = NOW()
        """),
        {"uid": user_id, "jid": job_id},
    )
    db.commit()


@shared_task(name="tasks.pipeline.stage6_finalize", bind=True)
def stage6_finalize(self, results, job_id_str: str) -> str:
    """Chord callback. `results` is the list of per-module run_module results."""
    db = get_db_session()
    try:
        job = db.query(UploadJob).filter(UploadJob.id == job_id_str).first()
        if not job:
            logger.warning(f"Finalize: job {job_id_str} not found")
            return "job_not_found"

        # ── 1. Module pass/fail summary ──
        status_counts = dict(
            db.execute(
                text("""
                    SELECT run_status, COUNT(*) AS n
                      FROM analytics_module_status
                     WHERE upload_job_id = :jid
                     GROUP BY run_status
                """),
                {"jid": job_id_str},
            ).fetchall()
        )
        n_failed = int(status_counts.get("failed", 0))
        n_completed = int(status_counts.get("completed", 0))

        if n_failed > 0:
            job.status = "completed_with_errors"
        else:
            job.status = "completed"
        job.completed_at = __import__("datetime").datetime.utcnow()
        db.commit()

        # ── 2. KPI snapshot ──
        try:
            _snapshot_kpis(db, job.user_id, job_id_str)
        except Exception as e:
            # KPI snapshot is non-fatal — analytics already in cache, the
            # dashboard home page will fall back to zero-filled defaults.
            logger.exception(f"KPI snapshot failed for job {job_id_str}: {e}")

        # ── 3. Denormalize AI fields back to customer/product rows ──
        # Best-effort — if A02 or A07 didn't run, these are no-ops.
        try:
            n_rfm = _denormalize_rfm(db, job.user_id, job_id_str)
            n_abc = _denormalize_abc(db, job.user_id, job_id_str)
            logger.info(f"[stage6] denormalized: {n_rfm} customer segments, {n_abc} product tiers")
        except Exception as e:
            logger.exception(f"Denormalization failed for job {job_id_str}: {e}")

        logger.info(
            f"[stage6] job {job_id_str} done — "
            f"modules completed={n_completed} failed={n_failed} "
            f"other={sum(v for k, v in status_counts.items() if k not in ('completed', 'failed'))}"
        )
        return (
            f"finalized: status={job.status}, "
            f"completed={n_completed}, failed={n_failed}"
        )
    finally:
        db.close()
