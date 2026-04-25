"""A15 — Revenue Forecasting (Prophet / Holt-Winters).

Primary: Prophet with tuned seasonality and changepoints.
Fallback: Holt-Winters exponential smoothing (statsmodels) or
          seasonal-naive + trend when neither library is available.
Writes to both analysis_results_cache (JSONB) and forecast_results table.
"""

import pandas as pd
import numpy as np
from sqlalchemy import text
from ._base import analytics_task, has_col

try:
    from prophet import Prophet
    _HAS_PROPHET = True
except ImportError:
    _HAS_PROPHET = False

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    _HAS_STATSMODELS = True
except ImportError:
    _HAS_STATSMODELS = False


def _holt_winters_forecast(daily, periods=90):
    """Holt-Winters exponential smoothing fallback.

    Automatically selects additive vs multiplicative seasonality and
    picks the best smoothing parameters via AIC.
    """
    daily = daily.sort_values("ds").reset_index(drop=True)
    y = daily["y"].values
    n = len(y)

    # Need at least 2 full seasonal cycles (14 days for weekly)
    seasonal_period = 7
    use_seasonal = n >= seasonal_period * 2

    best_model = None
    best_aic = np.inf

    configs = []
    if use_seasonal:
        configs.append({"seasonal": "add", "trend": "add", "seasonal_periods": seasonal_period})
        configs.append({"seasonal": "add", "trend": "add", "damped_trend": True, "seasonal_periods": seasonal_period})
        if (y > 0).all():
            configs.append({"seasonal": "mul", "trend": "add", "seasonal_periods": seasonal_period})
            configs.append({"seasonal": "mul", "trend": "add", "damped_trend": True, "seasonal_periods": seasonal_period})
    # Non-seasonal fallback
    configs.append({"seasonal": None, "trend": "add"})
    configs.append({"seasonal": None, "trend": "add", "damped_trend": True})

    for cfg in configs:
        try:
            model = ExponentialSmoothing(
                y,
                trend=cfg.get("trend"),
                seasonal=cfg.get("seasonal"),
                seasonal_periods=cfg.get("seasonal_periods"),
                damped_trend=cfg.get("damped_trend", False),
                initialization_method="estimated",
            ).fit(optimized=True)
            if model.aic < best_aic:
                best_aic = model.aic
                best_model = model
        except Exception:
            continue

    if best_model is None:
        return _seasonal_naive_forecast(daily, periods)

    forecast = best_model.forecast(periods)
    fitted = best_model.fittedvalues

    # Confidence interval from residuals
    residuals = y - fitted
    resid_std = max(np.std(residuals), np.mean(y) * 0.03)

    future_dates = pd.date_range(daily["ds"].max() + pd.Timedelta(days=1), periods=periods)

    # Widen CI over time (uncertainty grows with horizon)
    horizon_factor = np.sqrt(np.arange(1, periods + 1))
    ci_width = 1.96 * resid_std * horizon_factor / horizon_factor.max() * 2

    return pd.DataFrame({
        "ds": future_dates,
        "yhat": np.maximum(forecast.values, 0).round(2),
        "yhat_lower": np.maximum(forecast.values - ci_width, 0).round(2),
        "yhat_upper": (forecast.values + ci_width).round(2),
        "is_historical": False,
    })


def _seasonal_naive_forecast(daily, periods=90):
    """Seasonal-naive + trend fallback (no external libraries needed).

    1. Weekly seasonality via day-of-week averages.
    2. Trend from rolling mean projected forward.
    """
    daily = daily.sort_values("ds").reset_index(drop=True)
    n = len(daily)
    y = daily["y"].values

    daily["dow"] = daily["ds"].dt.dayofweek
    dow_means = daily.groupby("dow")["y"].mean()
    global_mean = y.mean()
    seasonal = dow_means - global_mean

    window = max(7, min(28, n // 3))
    rolling_trend = pd.Series(y).rolling(window, center=True, min_periods=3).mean()
    rolling_trend = rolling_trend.bfill().ffill().values

    x = np.arange(n)
    trend_coeffs = np.polyfit(x, rolling_trend, 1)
    slope, intercept = trend_coeffs[0], trend_coeffs[1]

    future_dates = pd.date_range(daily["ds"].max() + pd.Timedelta(days=1), periods=periods)
    future_x = np.arange(n, n + periods)
    future_trend = intercept + slope * future_x
    future_seasonal = np.array([seasonal.get(d, 0) for d in future_dates.dayofweek])
    yhat = future_trend + future_seasonal

    recent_residuals = y[-min(60, n):] - (intercept + slope * x[-min(60, n):])
    resid_std = max(np.std(recent_residuals), global_mean * 0.05)

    return pd.DataFrame({
        "ds": future_dates,
        "yhat": np.maximum(yhat, 0).round(2),
        "yhat_lower": np.maximum(yhat - 1.96 * resid_std, 0).round(2),
        "yhat_upper": (yhat + 1.96 * resid_std).round(2),
        "is_historical": False,
    })


@analytics_task("A15_prophet_forecast", "forecast")
def run_prophet_forecast(df, session, job_id):
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["created_at", amount_col])

    # Aggregate daily revenue
    daily = df.groupby(df["created_at"].dt.date).agg(
        y=(amount_col, "sum"),
    ).reset_index()
    daily.columns = ["ds", "y"]
    daily["ds"] = pd.to_datetime(daily["ds"])
    daily = daily.sort_values("ds")

    if len(daily) < 7:
        return {
            "historical": [],
            "forecast": [],
            "summary": "Not enough daily data points for forecasting (need >= 7)",
        }

    forecast_periods = 90

    if _HAS_PROPHET:
        # ── Prophet with tuned hyperparameters ──────────────────────────
        n_days = len(daily)
        model = Prophet(
            yearly_seasonality=n_days >= 365,
            weekly_seasonality=n_days >= 14,
            daily_seasonality=False,
            changepoint_prior_scale=0.1 if n_days < 180 else 0.05,
            seasonality_prior_scale=10,
            changepoint_range=0.85,
        )
        # Add monthly seasonality for medium-length series
        if 60 <= n_days < 365:
            model.add_seasonality(name="monthly", period=30.5, fourier_order=5)

        model.fit(daily[["ds", "y"]])

        future = model.make_future_dataframe(periods=forecast_periods)
        forecast = model.predict(future)

        hist_end = daily["ds"].max()
        hist = forecast[forecast["ds"] <= hist_end][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        hist["is_historical"] = True
        pred = forecast[forecast["ds"] > hist_end][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        pred["is_historical"] = False
        method = "prophet"

    elif _HAS_STATSMODELS:
        hist = daily[["ds"]].copy()
        hist["yhat"] = daily["y"]
        hist["yhat_lower"] = daily["y"]
        hist["yhat_upper"] = daily["y"]
        hist["is_historical"] = True
        pred = _holt_winters_forecast(daily, forecast_periods)
        method = "holt_winters"

    else:
        hist = daily[["ds"]].copy()
        hist["yhat"] = daily["y"]
        hist["yhat_lower"] = daily["y"]
        hist["yhat_upper"] = daily["y"]
        hist["is_historical"] = True
        pred = _seasonal_naive_forecast(daily, forecast_periods)
        method = "seasonal_naive"

    # Ensure no negative forecasts
    for col in ["yhat", "yhat_lower", "yhat_upper"]:
        pred[col] = pred[col].clip(lower=0)

    # Write to forecast_results table
    all_points = pd.concat([hist, pred], ignore_index=True)
    for _, row in all_points.iterrows():
        session.execute(
            text("""
                INSERT INTO forecast_results
                    (id, job_id, run_date, ds, yhat, yhat_lower, yhat_upper, is_historical)
                VALUES
                    (gen_random_uuid(), :job_id, CURRENT_DATE, :ds, :yhat, :lower, :upper, :is_hist)
            """),
            {
                "job_id": job_id,
                "ds": row["ds"].date() if hasattr(row["ds"], "date") else row["ds"],
                "yhat": round(float(row["yhat"]), 2),
                "lower": round(float(row["yhat_lower"]), 2),
                "upper": round(float(row["yhat_upper"]), 2),
                "is_hist": bool(row["is_historical"]),
            },
        )
    session.commit()

    def _to_records(frame):
        frame = frame.copy()
        frame["ds"] = frame["ds"].dt.strftime("%Y-%m-%d")
        return frame.round(2).to_dict("records")

    return {
        "method": method,
        "historical": _to_records(hist),
        "forecast": _to_records(pred),
        "forecast_periods": forecast_periods,
        "total_historical_days": len(daily),
        "forecast_summary": {
            "avg_daily_forecast": round(float(pred["yhat"].mean()), 2),
            "total_forecast_revenue": round(float(pred["yhat"].sum()), 2),
            "lower_bound_total": round(float(pred["yhat_lower"].sum()), 2),
            "upper_bound_total": round(float(pred["yhat_upper"].sum()), 2),
        },
    }
