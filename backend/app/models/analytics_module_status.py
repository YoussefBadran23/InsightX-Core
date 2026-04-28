"""AnalyticsModuleStatus — tracks which analytics modules can/cannot run per upload job.

Written by the preprocess task (Stage 3) after validating which columns are available.
Read by the frontend to show the user which modules are blocked and why.
"""

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.upload_job import UploadJob


class AnalyticsModuleStatus(UUIDMixin, TimestampMixin, Base):
    """
    One row per (upload_job × analytics_module).
    After CSV validation, the system writes 22 rows — one for each module —
    indicating whether it can run, and if not, which columns are missing.

    The frontend reads this to:
    1. Grey out blocked modules with a reason tooltip
    2. Show a popup with missing columns + "Map your column" CTA
    """
    __tablename__ = "analytics_module_status"
    __table_args__ = (
        UniqueConstraint("upload_job_id", "module_key", name="uq_module_status_job"),
    )

    upload_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("upload_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # e.g. "A01_revenue_summary", "A18_sentiment_analysis"
    module_key: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True
    )

    # Human-readable name — "Revenue Summary"
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Arabic name — "ملخص الإيرادات"
    module_name_ar: Mapped[str] = mapped_column(String(100), nullable=False)

    # One-line description of what this module does
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # TRUE = all required columns are present, module will run
    can_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Which Celery queue this module runs on
    queue: Mapped[str] = mapped_column(
        String(20), nullable=False, default="analytics"
    )

    # JSONB list of missing required column names
    # e.g. ["comment_text"] or ["return_flag", "product_id"]
    missing_required_columns: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    # JSONB list of missing optional column names (nice-to-have)
    missing_optional_columns: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    # "pending" | "running" | "completed" | "failed" | "skipped"
    run_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    # Error message if the module failed during execution
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    upload_job: Mapped["UploadJob"] = relationship("UploadJob")

    def __repr__(self) -> str:
        status = "OK" if self.can_run else f"BLOCKED ({self.missing_required_columns})"
        return f"<ModuleStatus {self.module_key} — {status}>"
