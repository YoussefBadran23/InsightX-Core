"""KPI router — dashboard summary and historical time-series."""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.daily_kpi_snapshot import DailyKpiSnapshot
from app.schemas.api import KpiSummaryOut, KpiHistoryOut, KpiHistoryItem, KpiDelta

router = APIRouter(prefix="/kpi", tags=["KPI"])


def _compute_delta(current: Decimal, previous: Decimal | None) -> KpiDelta:
    if previous is None or previous == 0:
        return KpiDelta(current=current, previous=previous, change_pct=None, direction="flat")
    delta = float((current - previous) / previous * 100)
    direction = "up" if delta > 0.5 else "down" if delta < -0.5 else "flat"
    return KpiDelta(current=current, previous=previous, change_pct=round(delta, 1), direction=direction)


@router.get("/summary", response_model=KpiSummaryOut, summary="Latest KPI snapshot with period-over-period deltas")
def get_kpi_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return the latest daily KPI snapshot along with MoM period-over-period deltas.

    Deltas compare current period vs the same-length period 30 days prior.
    """
    # Latest snapshot
    latest = (
        db.query(DailyKpiSnapshot)
        .filter(DailyKpiSnapshot.user_id == current_user.id)
        .order_by(desc(DailyKpiSnapshot.snapshot_date))
        .first()
    )
    if not latest:
        # Return zeros so the frontend can still render
        today = date.today()
        return KpiSummaryOut(
            snapshot_date=today,
            total_revenue=Decimal("0"),
            active_customers=0,
            new_customers=0,
            total_orders=0,
            avg_order_value=Decimal("0"),
            churn_rate=Decimal("0"),
            revenue_na=Decimal("0"),
            revenue_eu=Decimal("0"),
            revenue_apac=Decimal("0"),
            revenue_latam=Decimal("0"),
        )

    # Previous snapshot (30 days ago) for delta calculation
    prev_date = latest.snapshot_date - timedelta(days=30)
    previous = (
        db.query(DailyKpiSnapshot)
        .filter(
            DailyKpiSnapshot.user_id == current_user.id,
            DailyKpiSnapshot.snapshot_date <= prev_date
        )
        .order_by(desc(DailyKpiSnapshot.snapshot_date))
        .first()
    )

    return KpiSummaryOut(
        snapshot_date=latest.snapshot_date,
        total_revenue=latest.total_revenue,
        active_customers=latest.active_customers,
        new_customers=latest.new_customers,
        total_orders=latest.total_orders,
        avg_order_value=latest.avg_order_value,
        churn_rate=latest.churn_rate,
        revenue_na=latest.revenue_na,
        revenue_eu=latest.revenue_eu,
        revenue_apac=latest.revenue_apac,
        revenue_latam=latest.revenue_latam,
        revenue_delta=_compute_delta(latest.total_revenue, previous.total_revenue if previous else None),
        customers_delta=_compute_delta(Decimal(latest.active_customers), Decimal(previous.active_customers) if previous else None),
        orders_delta=_compute_delta(Decimal(latest.total_orders), Decimal(previous.total_orders) if previous else None),
        aov_delta=_compute_delta(latest.avg_order_value, previous.avg_order_value if previous else None),
    )


@router.get("/history", response_model=KpiHistoryOut, summary="Historical KPI time-series for charts")
def get_kpi_history(
    days: int = Query(default=30, ge=7, le=365, description="Number of history days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return daily KPI snapshots for the specified number of days — used by dashboard charts."""
    since = date.today() - timedelta(days=days)
    snapshots = (
        db.query(DailyKpiSnapshot)
        .filter(
            DailyKpiSnapshot.user_id == current_user.id,
            DailyKpiSnapshot.snapshot_date >= since
        )
        .order_by(DailyKpiSnapshot.snapshot_date)
        .all()
    )
    return KpiHistoryOut(
        days=days,
        items=[KpiHistoryItem.model_validate(s) for s in snapshots],
    )
