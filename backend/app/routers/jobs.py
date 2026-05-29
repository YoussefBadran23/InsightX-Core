"""Jobs router — upload job status and module tracking."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.upload_job import UploadJob
from app.models.analytics_module_status import AnalyticsModuleStatus
from app.schemas.api import JobOut, JobDetailOut, JobListOut, ModuleStatusOut

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _get_job_or_404(job_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> UploadJob:
    job = (
        db.query(UploadJob)
        .filter(UploadJob.id == job_id, UploadJob.user_id == user_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("", response_model=JobListOut, summary="List all upload jobs for current user")
def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return paginated list of upload jobs for the authenticated user."""
    query = (
        db.query(UploadJob)
        .filter(UploadJob.user_id == current_user.id)
        .order_by(UploadJob.created_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = max(1, (total + page_size - 1) // page_size)
    return JobListOut(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=[JobOut.model_validate(j) for j in items],
    )


@router.get("/{job_id}", response_model=JobDetailOut, summary="Get a single upload job with module statuses")
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full job detail including all 39 analytics module statuses."""
    job = _get_job_or_404(job_id, current_user.id, db)
    modules = (
        db.query(AnalyticsModuleStatus)
        .filter(AnalyticsModuleStatus.upload_job_id == job_id)
        .order_by(AnalyticsModuleStatus.module_key)
        .all()
    )
    out = JobDetailOut.model_validate(job)
    out.modules = [ModuleStatusOut.model_validate(m) for m in modules]
    return out


@router.get("/{job_id}/status", response_model=JobOut, summary="Lightweight job status polling endpoint")
def get_job_status(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lightweight polling endpoint — frontend calls this every 2s during upload.
    Returns only status + progress counters, no module detail.
    """
    job = _get_job_or_404(job_id, current_user.id, db)
    return JobOut.model_validate(job)


@router.get("/{job_id}/modules", response_model=list[ModuleStatusOut], summary="List analytics module statuses")
def get_job_modules(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all 39 analytics module eligibility statuses for a job."""
    _get_job_or_404(job_id, current_user.id, db)
    modules = (
        db.query(AnalyticsModuleStatus)
        .filter(AnalyticsModuleStatus.upload_job_id == job_id)
        .order_by(AnalyticsModuleStatus.module_key)
        .all()
    )
    return [ModuleStatusOut.model_validate(m) for m in modules]


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an upload job")
def delete_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a job and its analytics results."""
    job = _get_job_or_404(job_id, current_user.id, db)
    db.delete(job)
    db.commit()
