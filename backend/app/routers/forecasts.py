"""Forecasts router — reads from `analysis_results_cache` where module
`A15_prophet_forecast` stores its result. We no longer write to the legacy
`forecast_results` table; that path is preserved as a fallback for older data.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.analysis_results_cache import AnalysisResultsCache
from app.models.forecast_result import ForecastResult  # legacy fallback
from app.models.upload_job import UploadJob
from app.schemas.api import ForecastOut, ForecastPoint, ForecastSummary, ScenarioRequest

router = APIRouter(prefix="/forecasts", tags=["Forecasts"])

A15_KEY = "A15_prophet_forecast"


def _cache_to_forecast_out(
    cache_row: AnalysisResultsCache, job_id: uuid.UUID
) -> ForecastOut:
    """Convert an A15 cache row into the ForecastOut response shape."""
    data = cache_row.result_json or {}
    history = data.get("history", []) or []
    forecast = data.get("forecast", []) or []

    historical_points = [
        ForecastPoint(
            ds=str(h.get("date")),
            yhat=float(h.get("fitted") or 0),
            yhat_lower=float(h.get("lower") or 0),
            yhat_upper=float(h.get("upper") or 0),
            is_historical=True,
        )
        for h in history
        if h.get("date")
    ]

    forecast_points = [
        ForecastPoint(
            ds=str(f.get("date")),
            yhat=float(f.get("yhat") or 0),
            yhat_lower=float(f.get("lower") or 0),
            yhat_upper=float(f.get("upper") or 0),
            is_historical=False,
        )
        for f in forecast
        if f.get("date")
    ]

    pred_yhats = [p.yhat for p in forecast_points]
    pred_lowers = [p.yhat_lower for p in forecast_points]
    pred_uppers = [p.yhat_upper for p in forecast_points]

    summary = ForecastSummary(
        avg_daily_forecast=sum(pred_yhats) / len(pred_yhats) if pred_yhats else 0,
        total_forecast_revenue=sum(pred_yhats),
        lower_bound_total=sum(pred_lowers),
        upper_bound_total=sum(pred_uppers),
    )

    return ForecastOut(
        job_id=job_id,
        method=(data.get("summary", {}) or {}).get("model_engine", "prophet"),
        historical=historical_points,
        forecast=forecast_points,
        forecast_periods=len(forecast_points),
        total_historical_days=len(historical_points),
        forecast_summary=summary,
        computed_at=cache_row.computed_at,
    )


def _legacy_rows_to_forecast_out(
    rows: list[ForecastResult], job_id: uuid.UUID
) -> ForecastOut:
    """Convert legacy `forecast_results` table rows into ForecastOut."""
    historical = []
    forecast = []
    for r in rows:
        p = ForecastPoint(
            ds=str(r.ds),
            yhat=float(r.yhat),
            yhat_lower=float(r.yhat_lower),
            yhat_upper=float(r.yhat_upper),
            is_historical=r.is_historical,
        )
        if r.is_historical:
            historical.append(p)
        else:
            forecast.append(p)

    pred_yhats = [p.yhat for p in forecast]
    pred_lowers = [p.yhat_lower for p in forecast]
    pred_uppers = [p.yhat_upper for p in forecast]

    summary = ForecastSummary(
        avg_daily_forecast=sum(pred_yhats) / len(pred_yhats) if pred_yhats else 0,
        total_forecast_revenue=sum(pred_yhats),
        lower_bound_total=sum(pred_lowers),
        upper_bound_total=sum(pred_uppers),
    )

    latest_run = max(rows, key=lambda r: r.created_at) if rows else None

    return ForecastOut(
        job_id=job_id,
        method="prophet (legacy)",
        historical=historical,
        forecast=forecast,
        forecast_periods=len(forecast),
        total_historical_days=len(historical),
        forecast_summary=summary,
        computed_at=latest_run.created_at if latest_run else datetime.now(timezone.utc),
    )


def _load_forecast_for_job(job_id: uuid.UUID, db: Session) -> ForecastOut | None:
    """Try cache first (A15 module), then fall back to legacy forecast_results table."""
    cache_row = (
        db.query(AnalysisResultsCache)
        .filter(
            AnalysisResultsCache.upload_job_id == job_id,
            AnalysisResultsCache.analysis_type == A15_KEY,
        )
        .order_by(desc(AnalysisResultsCache.computed_at))
        .first()
    )
    if cache_row is not None:
        return _cache_to_forecast_out(cache_row, job_id)

    rows = (
        db.query(ForecastResult)
        .filter(ForecastResult.job_id == job_id)
        .order_by(ForecastResult.ds)
        .all()
    )
    if rows:
        return _legacy_rows_to_forecast_out(rows, job_id)
    return None


@router.get("/latest", response_model=ForecastOut, summary="Get most recent forecast run")
def get_latest_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most recent forecast (cache-first, legacy table fallback)."""
    latest_job = (
        db.query(UploadJob)
        .filter(UploadJob.user_id == current_user.id, UploadJob.status == "completed")
        .order_by(desc(UploadJob.completed_at))
        .first()
    )
    if not latest_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed upload jobs found. Upload a CSV first.",
        )

    out = _load_forecast_for_job(latest_job.id, db)
    if out is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No forecast data for the latest job. The A15 module may have "
                "been skipped (insufficient date range or missing columns)."
            ),
        )
    return out


@router.get("/{job_id}", response_model=ForecastOut, summary="Get forecast for a specific job")
def get_forecast_by_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return forecast results for a specific upload job."""
    job = db.query(UploadJob).filter(
        UploadJob.id == job_id, UploadJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    out = _load_forecast_for_job(job_id, db)
    if out is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No forecast data for this job")
    return out


@router.post("/scenario", response_model=dict, summary="Run a scenario forecast simulation")
def run_scenario(
    body: ScenarioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply scenario multipliers to the cached A15 forecast (no model re-run).

    Multipliers:
    - marketing_spend_pct: revenue lift factor (30% efficiency)
    - price_shift_pct:     price effect (70% pass-through)
    - seasonal_adjustment: low|medium|high amplitude modifier
    """
    job_id = body.job_id
    if not job_id:
        latest_job = (
            db.query(UploadJob)
            .filter(UploadJob.user_id == current_user.id, UploadJob.status == "completed")
            .order_by(desc(UploadJob.completed_at))
            .first()
        )
        if not latest_job:
            raise HTTPException(status_code=404, detail="No completed jobs found")
        job_id = latest_job.id
    else:
        # Verify ownership
        job = db.query(UploadJob).filter(
            UploadJob.id == job_id, UploadJob.user_id == current_user.id
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    base = _load_forecast_for_job(job_id, db)
    if base is None or not base.forecast:
        raise HTTPException(status_code=404, detail="No base forecast found for this job")

    # Apply scenario multipliers.
    seasonal_factor = {"low": 0.85, "medium": 1.0, "high": 1.15}.get(
        body.seasonal_adjustment, 1.0
    )
    # Fields are percentage points (e.g. 10 = +10%). Divide by 100 to get a rate.
    # marketing_spend_pct: 30% efficiency pass-through; price_shift_pct: 70% pass-through.
    marketing_lift = 1 + (body.marketing_spend_pct / 100) * 0.3
    price_effect = 1 + (body.price_shift_pct / 100) * 0.7
    total_multiplier = seasonal_factor * marketing_lift * price_effect

    adjusted = [
        {
            "ds": p.ds,
            "yhat": round(p.yhat * total_multiplier, 2),
            "yhat_lower": round(p.yhat_lower * total_multiplier, 2),
            "yhat_upper": round(p.yhat_upper * total_multiplier, 2),
            "is_historical": False,
        }
        for p in base.forecast
    ]

    total = sum(p["yhat"] for p in adjusted)
    return {
        "scenario_multiplier": round(total_multiplier, 4),
        "forecast": adjusted,
        "predictions": [p["yhat"] for p in adjusted],
        "total_forecast_revenue": round(total, 2),
        "parameters": body.model_dump(),
    }
