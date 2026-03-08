"""Insight model — LLaMA 3 generated bullet insights per analysis run."""

import uuid
from sqlalchemy import SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Insight(UUIDMixin, TimestampMixin, Base):
    """
    Stores the 3 AI-generated insight bullets produced by the
    Groq LLaMA 3 model (worker/tasks/insights.py) after each analysis run.

    UNIQUE(job_id, bullet_index) prevents duplicate bullets per run.
    bullet_index is 1, 2, or 3 — ordered display on the dashboard.
    """
    __tablename__ = "insights"

    # Links to the preprocess or forecast run that triggered this insight
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Which worker produced this insight:
    # preprocess | forecast | sentiment
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )

    # Ordering of the 3 AI bullet points (1, 2, or 3)
    bullet_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # The LLaMA 3 generated insight text
    bullet_text: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Insight job={self.job_id} source={self.source_type} "
            f"bullet={self.bullet_index}>"
        )
