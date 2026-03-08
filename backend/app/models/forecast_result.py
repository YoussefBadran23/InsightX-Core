"""ForecastResult model — Prophet time-series output with scenario parameters."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ForecastResult(UUIDMixin, TimestampMixin, Base):
    """
    One row per date per forecast run.
    Historical rows (is_historical=True) render as the solid blue line.
    Prediction rows (is_historical=False) render as the dashed purple line
    with yhat_lower/upper forming the 95% confidence shaded area.
    Scenario params stored per-row so any row is self-contained.
    """
    __tablename__ = "forecast_results"

    # Celery task ID or internal UUID for this forecast run
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    # Who triggered the forecast run
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    # The date the forecast was computed (not the forecast date)
    run_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Prophet date column — each row is one daily point on the chart
    ds: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Forecast center value (dashed purple line)
    yhat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Lower confidence bound (bottom of shaded area)
    yhat_lower: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Upper confidence bound (top of shaded area)
    yhat_upper: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # True = actual historical revenue (solid blue line)
    is_historical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # --- Scenario Simulation Panel parameters ---
    # "Marketing Spend Increase" slider — e.g. 15.00 means +15%
    scenario_marketing_spend_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    # "Expected Price Shift" slider — e.g. 5.00 means +5%, -10 means -10%
    scenario_price_shift_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    # "Seasonal Adjustment" toggle: low | medium | high
    scenario_seasonal_adj: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium"
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User", back_populates="forecast_results"
    )

    def __repr__(self) -> str:
        kind = "historical" if self.is_historical else "forecast"
        return f"<ForecastResult {kind} ds={self.ds} yhat={self.yhat}>"
