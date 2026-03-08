"""UploadJob model — tracks the full lifecycle of a CSV upload through the pipeline."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.order import Order
    from app.models.csv_column_mapping import CsvColumnMapping
    from app.models.analysis_results_cache import AnalysisResultsCache


class UploadJob(UUIDMixin, TimestampMixin, Base):
    """
    Tracks a single CSV upload through all 7 pipeline stages.
    Created at Stage 1 (FastAPI endpoint). Updated by each Celery task.
    Frontend polls GET /upload/status/{job_id} against this table.
    """
    __tablename__ = "upload_jobs"

    # FK to the user who triggered the upload
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    # S3 object key for the raw uploaded CSV
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    # Original filename shown to the user (e.g. "sales_march_2026.csv")
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Pipeline status — updated by each worker task:
    # pending → mapping → validating → inserting → analyzing → completed | failed
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )

    # Row counters — populated by validate_rows task
    rows_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Human-readable error if status = 'failed'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Celery task ID for direct Celery result-backend polling
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="upload_jobs")
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="upload_job"
    )
    csv_column_mappings: Mapped[list["CsvColumnMapping"]] = relationship(
        "CsvColumnMapping", back_populates="upload_job", cascade="all, delete-orphan"
    )
    analysis_results: Mapped[list["AnalysisResultsCache"]] = relationship(
        "AnalysisResultsCache", back_populates="upload_job"
    )

    def __repr__(self) -> str:
        return f"<UploadJob id={self.id} status={self.status} file={self.original_filename}>"
