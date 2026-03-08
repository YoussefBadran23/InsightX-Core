"""CsvColumnMapping model — auto-pipeline fuzzy header-to-column mapping log."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.upload_job import UploadJob


class CsvColumnMapping(UUIDMixin, TimestampMixin, Base):
    """
    Records every CSV header alongside the DB column it was mapped to.
    Written by the detect_columns Celery task (Stage 2).
    The system learns from history — same header maps instantly on next upload.
    Cascade-deleted when the parent upload_job is deleted.
    """
    __tablename__ = "csv_column_mappings"

    upload_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("upload_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Raw header string from the CSV e.g. "Sale Amt", "Order ID", "Cust_Email"
    csv_header: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    # Target table e.g. "orders", "customers", "products"
    mapped_table: Mapped[str] = mapped_column(String(100), nullable=False)
    # Target column e.g. "total_amount", "email", "sku"
    mapped_column_name: Mapped[str] = mapped_column(
        "mapped_column", String(100), nullable=False
    )

    # 0.0000–1.0000; >= 0.85 = auto-confirmed, 0.60-0.84 = used with low confidence
    match_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    # How the mapping was determined:
    # exact | fuzzy (RapidFuzz) | semantic (sentence-transformers) | historical
    match_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default="fuzzy"
    )

    # True = pipeline will use this mapping; False = skipped (below threshold)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    upload_job: Mapped["UploadJob"] = relationship(
        "UploadJob", back_populates="csv_column_mappings"
    )

    def __repr__(self) -> str:
        return (
            f"<CsvColumnMapping '{self.csv_header}' → "
            f"{self.mapped_table}.{self.mapped_column_name} "
            f"({self.match_method}, score={self.match_score})>"
        )
