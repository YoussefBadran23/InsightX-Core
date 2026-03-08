"""AnalysisResultsCache model — JSONB cache for all 22 analytics modules."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin

if TYPE_CHECKING:
    from app.models.upload_job import UploadJob


class AnalysisResultsCache(UUIDMixin, Base):
    """
    Stores the computed output of every analytics module as a JSONB blob.
    Frontend reads from this table — zero recomputation on page load.
    Celery sets is_stale=True when a new upload starts, then False after recompute.

    UNIQUE(analysis_type, upload_job_id) prevents duplicate module outputs
    for the same upload job.

    Supported analysis_type values (22 modules):
    rfm | cohort | revenue | basket | forecast | anomaly | clv | sentiment |
    segmentation | abc_tier | margin | churn | geo | seasonality | funnel |
    payment_channel | attribution | returns | fulfillment | supplier |
    correlation | demographic
    """
    __tablename__ = "analysis_results_cache"

    # Which analytics module produced this result
    analysis_type: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True
    )
    # The upload job that triggered this computation
    upload_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("upload_jobs.id"), nullable=True, index=True
    )

    # Full module output consumed directly by the API → frontend
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Timestamp of last computation
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Flipped TRUE when a new upload starts; FALSE after module recomputes
    is_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # How long this module took to run — for performance monitoring
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    upload_job: Mapped["UploadJob | None"] = relationship(
        "UploadJob", back_populates="analysis_results"
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisResultsCache type={self.analysis_type} "
            f"stale={self.is_stale} computed={self.computed_at}>"
        )
