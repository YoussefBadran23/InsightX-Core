"""Customer model — profiles, RFM, CLV, cohort, and segmentation."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Date, DateTime, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.order import Order


class Customer(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Customer entity. Populated during CSV ingest.
    Denormalized fields (total_orders, lifetime_value) updated by
    the insert_orders worker task on each upload.
    """
    __tablename__ = "customers"

    # The "CUS-001" format shown in the Customer Profiles UI table.
    external_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, unique=True, index=True
    )

    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Country display text e.g. "United States" — shown in profile table
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # ISO 3166-1 alpha-2 e.g. "US" — used for flag emoji and geo analytics
    country_code: Mapped[str | None] = mapped_column(
        String(2), nullable=True, index=True
    )
    # NA | EU | APAC | LATAM — denormalized for Revenue by Region chart
    region: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    # "Oct 24, 2023" shown in Customer Profiles table
    first_purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Denormalized counters (updated by insert_orders task) ---
    # Shown directly in Customer Profiles table columns
    total_orders: Mapped[int] = mapped_column(default=0, nullable=False)
    lifetime_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), index=True
    )
    # Annual Recurring Revenue — displayed in Segmentation screen
    arr: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    # --- Analytics outputs (written by analytics worker tasks) ---
    # engagement_score: 0–100; Y-axis of segmentation bubble chart
    engagement_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    # ai_segment: written by A09 K-Means; shown as badge in Customer Profiles
    # Values: vip_champion | loyalist | at_risk | new_potential | undetermined
    ai_segment: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    # last_active_at: drives the At-Risk rule (> 90 days)
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # churn_risk_score: 0.0–1.0; written by A12 Logistic Regression
    churn_risk_score: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2), nullable=True
    )
    # clv_predicted: future value from A07 BG/NBD model
    clv_predicted: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    # cohort_month: DATE_TRUNC('month', first_purchase_date) — core of A02 Cohort
    cohort_month: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True
    )
    # rfm_score: composite score e.g. "555" from A01 RFM
    rfm_score: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # rfm_segment: named segment e.g. "Champions" from A01 RFM
    rfm_segment: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    # --- Demographics (from CSV if available) ---
    # age_group: "18-24", "25-34", etc. — for A22 Demographic Segmentation
    age_group: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    # gender: for A22 Demographic Segmentation
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="customer"
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} email={self.email} segment={self.ai_segment}>"
