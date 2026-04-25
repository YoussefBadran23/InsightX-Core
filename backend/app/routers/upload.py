"""CSV Upload Router — handles receiving files and dispatching to Celery."""

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.celery_client import celery_client
from app.core.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.upload_job import UploadJob
from app.models.user import User

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

_MAX_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel"}


@router.post("/csv", status_code=status.HTTP_201_CREATED)
async def upload_csv(
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    Receives a CSV file, saves it to local storage, creates an UploadJob
    record, and dispatches the Celery mapping task — all in one transaction.
    """
    # --- Filename / extension check ---
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    # --- MIME type check ---
    if file.content_type and file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type '{file.content_type}'. Upload a CSV file.",
        )

    # --- Read and enforce size limit ---
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > _MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # --- Quick structural check: ensure there is at least a header row ---
    first_line = data.split(b"\n")[0].decode("utf-8", errors="replace").strip()
    if not first_line:
        raise HTTPException(status_code=400, detail="CSV file has no header row.")

    # --- Persist file ---
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    try:
        with open(file_path, "wb") as buf:
            buf.write(data)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # --- DB record + Celery dispatch in one transaction ---
    upload_job = UploadJob(
        user_id=current_user.id,
        s3_key=unique_filename,
        original_filename=file.filename,
        status="pending",
    )
    db.add(upload_job)
    db.flush()  # obtain upload_job.id without committing yet

    try:
        # Commit BEFORE sending task to avoid race condition
        db.commit()
        db.refresh(upload_job)

        task = celery_client.send_task(
            "tasks.csv.process_csv", args=[str(upload_job.id)]
        )
    except Exception as e:
        db.rollback()
        os.remove(file_path)
        raise HTTPException(
            status_code=503,
            detail="Task queue unavailable. Please try again later.",
        )

    upload_job.celery_task_id = task.id
    db.commit()

    return {
        "message": "File uploaded successfully. Processing started.",
        "job_id": str(upload_job.id),
        "task_id": task.id,
    }
