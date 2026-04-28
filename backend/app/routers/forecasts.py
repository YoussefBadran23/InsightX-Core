"""Forecasts router — retrieve forecast results and run scenario simulations."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.forecast_result import ForecastResult
from app.models.upload_job import UploadJob
from app.schemas.api import ForecastOut, ForecastPoint, ForecastSummary, ScenarioRequest

router = APIRouter(prefix="/forecasts", tags=["Forecasts"])


def _rows_to_forecast_out(rows: list[ForecastResult], job_id: uuid.UUID) -> ForecastOut:
    """Convert DB rows into ForecastOut schema."""
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
        method="prophet",
        historical=historical,
        forecast=forecast,
        forecast_periods=len(forecast),
        total_historical_days=len(historical),
        forecast_summary=summary,
        computed_at=latest_run.created_at if latest_run else datetime.now(timezone.utc),
    )


@router.get("/latest", response_model=ForecastOut, summary="Get most recent forecast run")
def get_latest_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most recent forecast run for this user."""
    # Find latest job for this user
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

    rows = (
        db.query(ForecastResult)
        .filter(ForecastResult.job_id == latest_job.id)
        .order_by(ForecastResult.ds)
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast data for the latest job. The A15 module may not have run.",
        )
    return _rows_to_forecast_out(rows, latest_job.id)


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

    rows = (
        db.query(ForecastResult)
        .filter(ForecastResult.job_id == job_id)
        .order_by(ForecastResult.ds)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No forecast data for this job")
    return _rows_to_forecast_out(rows, job_id)


@router.post("/scenario", response_model=dict, summary="Run a scenario forecast simulation")
def run_scenario(
    body: ScenarioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a scenario-adjusted forecast.

    Applies multipliers based on scenario sliders:
    - marketing_spend_pct: revenue lift factor
    - price_shift_pct: price multiplier effect
    - seasonal_adjustment: low/medium/high amplitude modifier

    Returns adjusted forecast; does NOT re-run the ML model.
    """
    # Get the base forecast
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

    rows = (
        db.query(ForecastResult)
        .filter(ForecastResult.job_id == job_id, ForecastResult.is_historical.is_(False))
        .order_by(ForecastResult.ds)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No base forecast found")

    # Apply scenario multipliers
    seasonal_factor = {"low": 0.85, "medium": 1.0, "high": 1.15}[body.seasonal_adjustment]
    marketing_lift = 1 + (body.marketing_spend_pct / 100) * 0.3   # 30% efficiency
    price_effect = 1 + (body.price_shift_pct / 100) * 0.7          # 70% pass-through
    total_multiplier = seasonal_factor * marketing_lift * price_effect

    adjusted = [
        {
            "ds": str(r.ds),
            "yhat": round(float(r.yhat) * total_multiplier, 2),
            "yhat_lower": round(float(r.yhat_lower) * total_multiplier, 2),
            "yhat_upper": round(float(r.yhat_upper) * total_multiplier, 2),
            "is_historical": False,
        }
        for r in rows
    ]

    total = sum(p["yhat"] for p in adjusted)
    return {
        "scenario_multiplier": round(total_multiplier, 4),
        "forecast": adjusted,
        "total_forecast_revenue": round(total, 2),
        "parameters": body.model_dump(),
    }
