"""Analytics router — serves cached module results from analysis_results_cache."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.analysis_results_cache import AnalysisResultsCache
from app.models.upload_job import UploadJob
from app.schemas.api import AnalyticsResultOut, AnalyticsSummaryOut

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Map URL segment → analysis_type stored in DB
_ANALYSIS_TYPE_MAP: dict[str, str] = {
    "revenue": "revenue",
    "rfm": "rfm",
    "cohort": "cohort",
    "basket": "basket",
    "margin": "margin",
    "geographic": "geo",
    "abc": "abc_tier",
    "aov": "aov_trends",
    "products": "top_n",
    "clv-stats": "clv_stats",
    "order-status": "order_status",
    "discount": "discount",
    "growth": "growth",
    "channel": "channel",
    "forecast": "forecast",
    "anomaly": "anomaly",
    "clv": "clv",
    "sentiment": "sentiment",
    "segmentation": "segmentation",
    "churn": "churn",
    "returns": "returns",
    "fulfillment": "fulfillment",
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

    # Verify ownership
    job = db.query(UploadJob).filter(
        UploadJob.id == job_id, UploadJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    results = (
        db.query(AnalysisResultsCache)
        .filter(AnalysisResultsCache.upload_job_id == job_id)
        .order_by(AnalysisResultsCache.analysis_type)
        .all()
    )

    modules: dict[str, Any] = {r.analysis_type: r.result_json for r in results}
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

    # Verify the job belongs to this user
    job = db.query(UploadJob).filter(
        UploadJob.id == job_id, UploadJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    result = _get_result(db_type, job_id, db)
    return AnalyticsResultOut.model_validate(result)
