"""DailyKpiSnapshot model — pre-aggregated KPIs for period-over-period dashboard deltas."""

from datetime import date
from decimal import Decimal
from sqlalchemy import Date, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class DailyKpiSnapshot(UUIDMixin, TimestampMixin, Base):
    """
    One row per calendar day. Pre-aggregated from the orders table.
    Populated by the finalize Celery task at end of each upload,
    and by the nightly Celery Beat task (00:05 UTC).

    Enables O(1) period-over-period comparison for dashboard KPI cards:
    - "+12% Total Revenue vs last month"
    - "+5% Active Customers"
    - "-0.5% Churn Rate"

    Without this table, every dashboard load would require a full
    multi-table aggregate over all historical orders.
    """
    __tablename__ = "daily_kpi_snapshots"

    # One row per day — UNIQUE enforced
    snapshot_date: Mapped[date] = mapped_column(
        Date, nullable=False, unique=True, index=True
    )

    # --- Core KPIs (shown on Dashboard Home cards) ---
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    active_customers: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    new_customers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Stored as decimal e.g. 0.0240 = 2.4% (shown as "2.4% Churn Rate" on dashboard)
    churn_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("0.0000")
    )
    avg_order_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    # --- Revenue by Region (Revenue by Region bar chart on Dashboard) ---
    revenue_na: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    revenue_eu: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    revenue_apac: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    revenue_latam: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    def __repr__(self) -> str:
        return (
            f"<DailyKpiSnapshot date={self.snapshot_date} "
            f"revenue={self.total_revenue} customers={self.active_customers}>"
        )
