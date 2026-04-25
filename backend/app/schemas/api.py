"""Pydantic schemas for Jobs, Analytics, KPI, Customers, Products, Forecasts, Insights."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

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


class CustomerListOut(PaginatedResponse):
    items: list[CustomerOut]


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


class ProductListOut(PaginatedResponse):
    items: list[ProductOut]


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
