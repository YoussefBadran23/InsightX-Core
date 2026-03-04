"""Placeholder — Step 11 (Phase 3): Prophet-based time-series forecasting."""

from celery_app import celery_app


@celery_app.task(bind=True, name="tasks.forecast.run_forecast")
def run_forecast(self, job_id: str):
    """Run ProphetStrategy and save yhat/yhat_lower/yhat_upper to DB."""
    # TODO: Implement in Phase 3 (Step 11)
    raise NotImplementedError("Forecast task not yet implemented.")
