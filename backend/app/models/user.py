"""User model — authentication, roles, and dashboard widget layout."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.upload_job import UploadJob
    from app.models.forecast_result import ForecastResult


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Platform user. Stores auth credentials, role, and persisted
    dashboard widget layout (from Analytics Edit Mode 'Save Layout').
    """
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Roles: 'admin' | 'analyst' | 'user'
    # Shown in sidebar bottom e.g. "Alex Morgan / Admin"
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="user", index=True
    )

    # Persisted drag-and-drop layout from Analytics Edit Mode "Save Layout".
    # Shape: {"layout": [{"i": "revenue_chart", "x": 0, "y": 0, "w": 8, "h": 2}]}
    widget_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    # "Forgot password?" flow — stores hashed reset token
    reset_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    upload_jobs: Mapped[list["UploadJob"]] = relationship(
        "UploadJob", back_populates="user"
    )
    forecast_results: Mapped[list["ForecastResult"]] = relationship(
        "ForecastResult", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
