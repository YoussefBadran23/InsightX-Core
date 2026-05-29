"""Analytics router — serves cached module results from analysis_results_cache."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.analysis_results_cache import AnalysisResultsCache
from app.models.upload_job import UploadJob
from app.schemas.api import AnalyticsResultOut, AnalyticsSummaryOut

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Map URL segment → module_key stored in `analysis_results_cache.analysis_type`.
# The pipeline now stores each module's unique key (e.g. 'A01_revenue_summary')
# in that column. We keep short URL aliases for nice URLs (`/analytics/revenue`
# → `A01_revenue_summary`). If the URL segment IS already a module key (e.g.
# `/analytics/A01_revenue_summary`), it passes through unchanged.
_ANALYSIS_TYPE_MAP: dict[str, str] = {
    "revenue": "A01_revenue_summary",
    "rfm": "A02_rfm_scoring",
    "basket": "A03_market_basket",
    "margin": "A04_gross_margin",
    "cohort": "A05_cohort_retention",
    "geographic": "A06_geographic_revenue",
    "geo": "A06_geographic_revenue",
    "abc": "A07_abc_classification",
    "abc_tier": "A07_abc_classification",
    "aov": "A08_aov_trends",
    "aov_trends": "A08_aov_trends",
    "top-n": "A09_top_n_products",
    "top_n": "A09_top_n_products",
    "products": "A09_top_n_products",
    "clv-stats": "A10_customer_lifetime",
    "lifetime": "A10_customer_lifetime",
    "order-status": "A11_order_status",
    "order_status": "A11_order_status",
    "status": "A11_order_status",
    "discount": "A12_discount_impact",
    "growth": "A13_growth_rates",
    "channel": "A14_acquisition_channel",
    "acquisition": "A14_acquisition_channel",
    "forecast": "A15_prophet_forecast",
    "anomaly": "A16_anomaly_detection",
    "clv": "A17_clv_prediction",
    "sentiment": "A18_sentiment_analysis",
}


def _resolve_latest_job(user_id: uuid.UUID, db: Session) -> uuid.UUID | None:
    """Return the most recently completed job for this user."""
    job = (
        db.query(UploadJob)
        .filter(UploadJob.user_id == user_id, UploadJob.status == "completed")
        .order_by(UploadJob.completed_at.desc())
        .first()
    )
    return job.id if job else None


def _get_result(
    analysis_type: str,
    job_id: uuid.UUID,
    db: Session,
) -> AnalysisResultsCache:
    result = (
        db.query(AnalysisResultsCache)
        .filter(
            AnalysisResultsCache.analysis_type == analysis_type,
            AnalysisResultsCache.upload_job_id == job_id,
        )
        .order_by(AnalysisResultsCache.computed_at.desc())
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cached results for '{analysis_type}'. Run an upload first.",
        )
    return result


@router.get(
    "/summary",
    response_model=AnalyticsSummaryOut,
    summary="Get all analytics module results for an upload job",
)
def get_analytics_summary(
    job_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all cached analytics results for a given job in one response."""
    if not job_id:
        job_id = _resolve_latest_job(current_user.id, db)
        if not job_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No completed upload jobs found.",
            )
        # _resolve_latest_job already filters by user_id — ownership verified
    else:
        owned = db.execute(
            select(UploadJob.id).where(
                UploadJob.id == job_id, UploadJob.user_id == current_user.id
            )
        ).scalar()
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Column projection: only fetch the two fields we actually use
    rows = db.execute(
        select(AnalysisResultsCache.analysis_type, AnalysisResultsCache.result_json)
        .where(AnalysisResultsCache.upload_job_id == job_id)
        .order_by(AnalysisResultsCache.analysis_type)
    ).all()

    modules: dict[str, Any] = {r.analysis_type: r.result_json for r in rows}
    return AnalyticsSummaryOut(job_id=job_id, modules=modules)


@router.get(
    "/{analysis_type}",
    response_model=AnalyticsResultOut,
    summary="Get cached analytics result for a specific module",
)
def get_analytics(
    analysis_type: str,
    job_id: uuid.UUID | None = Query(default=None, description="Filter by specific upload job"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve pre-computed analytics result. Zero recomputation on page load.

    Uses the latest completed job if job_id is not provided.
    """
    db_type = _ANALYSIS_TYPE_MAP.get(analysis_type, analysis_type)

    if not job_id:
        job_id = _resolve_latest_job(current_user.id, db)
        if not job_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No completed upload jobs found. Upload a CSV first.",
            )
        # _resolve_latest_job already filters by user_id — ownership verified
    else:
        owned = db.execute(
            select(UploadJob.id).where(
                UploadJob.id == job_id, UploadJob.user_id == current_user.id
            )
        ).scalar()
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    result = _get_result(db_type, job_id, db)
    return AnalyticsResultOut.model_validate(result)
