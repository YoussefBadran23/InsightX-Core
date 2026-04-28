"""Insights router — retrieve LLM-generated business insights."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.insight import Insight
from app.models.upload_job import UploadJob
from app.schemas.api import InsightOut, InsightsOut

router = APIRouter(prefix="/insights", tags=["Insights"])


def _insight_to_out(insight: Insight) -> InsightOut:
    return InsightOut(
        id=insight.id,
        job_id=insight.job_id,
        title=insight.source_type,
        body=insight.bullet_text,
        insight_type=insight.source_type,
        priority=insight.bullet_index,
        created_at=insight.created_at,
    )


@router.get("/latest", response_model=InsightsOut, summary="Get most recent AI insights")
def get_latest_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most recent set of LLM-generated business insights."""
    # Find latest completed job
    latest_job = (
        db.query(UploadJob)
        .filter(UploadJob.user_id == current_user.id, UploadJob.status == "completed")
        .order_by(desc(UploadJob.completed_at))
        .first()
    )
    if not latest_job:
        return InsightsOut(job_id=None, insights=[])

    insights = (
        db.query(Insight)
        .filter(Insight.job_id == latest_job.id)
        .order_by(Insight.bullet_index)
        .all()
    )
    return InsightsOut(
        job_id=latest_job.id,
        insights=[_insight_to_out(i) for i in insights],
    )


@router.get("/{job_id}", response_model=InsightsOut, summary="Get AI insights for a specific job")
def get_insights_by_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all LLM insights for a specific upload job."""
    job = db.query(UploadJob).filter(
        UploadJob.id == job_id, UploadJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    insights = (
        db.query(Insight)
        .filter(Insight.job_id == job_id)
        .order_by(Insight.bullet_index)
        .all()
    )
    return InsightsOut(
        job_id=job_id,
        insights=[_insight_to_out(i) for i in insights],
    )
