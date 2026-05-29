"""Pydantic schemas for Jobs, Analytics, KPI, Customers, Products, Forecasts, Insights."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


# ─────────────────────────────────── SHARED ──────────────────────────────────

class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int


# ─────────────────────────────────── JOBS ────────────────────────────────────

class ModuleStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    module_key: str
    module_name: str
    module_name_ar: str
    description: str
    can_run: bool
    queue: str
    run_status: str
    missing_required_columns: list[str] | None = None
    missing_optional_columns: list[str] | None = None
    error_message: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str | None
    status: str
    rows_total: int | None
    rows_processed: int
    rows_failed: int
    error_message: str | None
    # ISO 4217 (e.g. 'USD','EGP','BRL') — set in stage3 from the CSV's `currency`
    # column mode, or chosen by the user at upload time. Frontend uses this as
    # the `from` argument to `formatMoney` so values FX-convert correctly.
    source_currency: str | None = "USD"
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @computed_field  # type: ignore[misc]
    @property
    def progress(self) -> int:
        """Pipeline progress 0-100 derived from job status.

        Returned in every poll response so the frontend never has to guess —
        the old client-side ``Math.min(p + 2, 94)`` fallback is only reached
        when this field is absent (older backend), so adding it here silently
        fixes the 94% freeze without any frontend logic change required.
        """
        _PCT: dict[str, int] = {
            "pending":               5,
            "sniffing":             15,
            "validating":           35,
            "inserting":            55,
            "analyzing":            75,
            "completed":           100,
            "completed_with_errors": 100,
            "failed":                0,
        }
        return _PCT.get(self.status or "", 10)

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class JobDetailOut(JobOut):
    modules: list[ModuleStatusOut] = []


class JobListOut(PaginatedResponse):
    items: list[JobOut]


# ─────────────────────────────────── ANALYTICS ───────────────────────────────

class AnalyticsResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_type: str
    upload_job_id: uuid.UUID | None
    result_json: dict[str, Any]
    computed_at: datetime
    is_stale: bool
    duration_ms: int | None


class AnalyticsSummaryOut(BaseModel):
    job_id: uuid.UUID
    modules: dict[str, Any]  # module_key → result_json


# ─────────────────────────────────── KPI ─────────────────────────────────────

class KpiDelta(BaseModel):
    current: Decimal
    previous: Decimal | None
    change_pct: float | None  # e.g. 12.5 = +12.5%
    direction: str  # 'up' | 'down' | 'flat'


class KpiSummaryOut(BaseModel):
    snapshot_date: date
    total_revenue: Decimal
    active_customers: int
    new_customers: int
    total_orders: int
    avg_order_value: Decimal
    churn_rate: Decimal
    revenue_na: Decimal
    revenue_eu: Decimal
    revenue_apac: Decimal
    revenue_latam: Decimal
    # Native currency of the underlying CSV data (from the latest completed job).
    # Frontend formats every money value as
    #   formatMoney(value, user.preferred_currency, { from: source_currency })
    # so FX conversion is end-to-end correct, not just symbol swap.
    source_currency: str = "USD"
    # Period-over-period deltas
    revenue_delta: KpiDelta | None = None
    customers_delta: KpiDelta | None = None
    orders_delta: KpiDelta | None = None
    aov_delta: KpiDelta | None = None


class KpiHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_date: date
    total_revenue: Decimal
    active_customers: int
    total_orders: int
    avg_order_value: Decimal


class KpiHistoryOut(BaseModel):
    days: int
    items: list[KpiHistoryItem]


# ─────────────────────────────────── CUSTOMERS ───────────────────────────────

class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str | None
    email: str
    full_name: str | None
    country: str | None
    region: str | None
    first_purchase_date: date | None
    total_orders: int
    lifetime_value: Decimal
    ai_segment: str | None
    churn_risk_score: Decimal | None
    clv_predicted: Decimal | None
    rfm_segment: str | None
    rfm_score: str | None
    last_active_at: datetime | None
    is_active: bool


class CustomerDetailOut(CustomerOut):
    arr: Decimal
    engagement_score: Decimal
    cohort_month: date | None
    age_group: str | None
    gender: str | None
    country_code: str | None


class CustomerListSummary(BaseModel):
    """Aggregates over the FULL filtered customer set (not the visible page).

    Powers the cards at the top of `/dashboard/customers`. Mirrors the
    products page pattern so the cards stay consistent with the user's
    search / segment / region filter rather than reflecting only the 25
    rows on screen.
    """
    avg_lifetime_value: Decimal
    vip_count: int
    at_risk_count: int


class CustomerListOut(PaginatedResponse):
    items: list[CustomerOut]
    summary: CustomerListSummary


# ─────────────────────────────────── PRODUCTS ────────────────────────────────

class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    category: str
    unit_price: Decimal
    cost_price: Decimal | None
    stock_qty: int
    low_stock_threshold: int
    abc_tier: str | None
    return_rate: Decimal | None
    total_revenue: Decimal
    total_units_sold: int
    is_active: bool
    is_low_stock: bool
    gross_margin_pct: Decimal | None


class ProductListSummary(BaseModel):
    """Aggregates computed over the FULL filtered set (not just the current page).

    Powers the cards at the top of `/dashboard/products`. Previously the cards
    were computed on the frontend from the 25-row page slice, so the values
    flipped when the user paged. These are now SQL aggregates honoring the
    same search / category / abc_tier / low_stock filters as the list query.
    """
    inventory_value: Decimal
    low_stock_count: int
    categories_count: int


class ProductListOut(PaginatedResponse):
    items: list[ProductOut]
    summary: ProductListSummary


# ─────────────────────────────────── FORECASTS ───────────────────────────────

class ForecastPoint(BaseModel):
    ds: str          # ISO date string "YYYY-MM-DD"
    yhat: float
    yhat_lower: float
    yhat_upper: float
    is_historical: bool


class ForecastSummary(BaseModel):
    avg_daily_forecast: float
    total_forecast_revenue: float
    lower_bound_total: float
    upper_bound_total: float


class ForecastOut(BaseModel):
    job_id: uuid.UUID
    method: str
    historical: list[ForecastPoint]
    forecast: list[ForecastPoint]
    forecast_periods: int
    total_historical_days: int
    forecast_summary: ForecastSummary
    computed_at: datetime


class ScenarioRequest(BaseModel):
    marketing_spend_pct: float = Field(default=0.0, ge=-50, le=50)
    price_shift_pct: float = Field(default=0.0, ge=-10, le=20)
    seasonal_adjustment: str = Field(default="medium", pattern="^(low|medium|high)$")
    job_id: uuid.UUID | None = None


# ─────────────────────────────────── INSIGHTS ────────────────────────────────

class InsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID | None
    title: str | None
    body: str
    insight_type: str | None
    priority: int | None
    created_at: datetime


class InsightsOut(BaseModel):
    job_id: uuid.UUID | None
    insights: list[InsightOut]
