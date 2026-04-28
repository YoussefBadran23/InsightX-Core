"""A15 — Revenue Forecasting (Optimized & Complete)."""
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

# RAM Optimization
COLS = ["created_at", "total_amount", "net_amount"]

def _holt_winters_forecast(daily, periods=90):
    daily = daily.sort_values("ds").reset_index(drop=True)
    y = daily["y"].values
    n = len(y)
    seasonal_period = 7
    use_seasonal = n >= seasonal_period * 2
    best_model, best_aic = None, np.inf
    configs = [{"seasonal": "add", "trend": "add", "seasonal_periods": seasonal_period}] if use_seasonal else []
    configs.append({"seasonal": None, "trend": "add"})

    for cfg in configs:
        try:
            model = ExponentialSmoothing(y, trend=cfg.get("trend"), seasonal=cfg.get("seasonal"), 
                                         seasonal_periods=cfg.get("seasonal_periods")).fit(optimized=True)
            if model.aic < best_aic:
                best_aic, best_model = model.aic, model
        except: continue

    if not best_model: return _seasonal_naive_forecast(daily, periods)
    forecast = best_model.forecast(periods)
    future_dates = pd.date_range(daily["ds"].max() + pd.Timedelta(days=1), periods=periods)
    return pd.DataFrame({"ds": future_dates, "yhat": np.maximum(forecast.values, 0), 
                         "yhat_lower": np.maximum(forecast.values * 0.8, 0), "yhat_upper": forecast.values * 1.2, "is_historical": False})

def _seasonal_naive_forecast(daily, periods=90):
    n = len(daily)
    y = daily["y"].values
    future_dates = pd.date_range(daily["ds"].max() + pd.Timedelta(days=1), periods=periods)
    avg_val = y.mean()
    return pd.DataFrame({"ds": future_dates, "yhat": avg_val, "yhat_lower": avg_val * 0.7, 
                         "yhat_upper": avg_val * 1.3, "is_historical": False})

@analytics_task("A15_prophet_forecast", "forecast", required_cols=COLS)
def run_prophet_forecast(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at", amount_col])
    daily = df.groupby(df["created_at"].dt.date).agg(y=(amount_col, "sum")).reset_index()
    daily.columns, daily["ds"] = ["ds", "y"], pd.to_datetime(daily["ds"])
    
    if len(daily) < 7: return {"summary": "Insufficient data"}

    forecast_periods = 90
    if _HAS_PROPHET:
        model = Prophet(yearly_seasonality=len(daily)>=365, weekly_seasonality=True, daily_seasonality=False)
        model.fit(daily[["ds", "y"]])
        forecast = model.predict(model.make_future_dataframe(periods=forecast_periods))
        hist = forecast[forecast["ds"] <= daily["ds"].max()][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        pred = forecast[forecast["ds"] > daily["ds"].max()][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        method = "prophet"
    else:
        pred = _holt_winters_forecast(daily, forecast_periods)
        hist = daily.rename(columns={"y": "yhat"}).assign(yhat_lower=lambda x: x.yhat, yhat_upper=lambda x: x.yhat)
        method = "holt_winters"

    hist["is_historical"], pred["is_historical"] = True, False
    all_points = pd.concat([hist, pred])
    
    # PERFORMANCE WIN: Batch Insert Forecast Results
    batch = [{"job_id": job_id, "ds": r.ds.date(), "yhat": round(float(r.yhat), 2), "lower": round(float(r.yhat_lower), 2), 
              "upper": round(float(r.yhat_upper), 2), "is_hist": bool(r.is_historical)} for r in all_points.itertuples()]
    session.execute(text("INSERT INTO forecast_results (id, job_id, run_date, ds, yhat, yhat_lower, yhat_upper, is_historical) "
                         "VALUES (gen_random_uuid(), :job_id, CURRENT_DATE, :ds, :yhat, :lower, :upper, :is_hist)"), batch)
    session.commit()

    return {"method": method, "forecast_summary": {"total_revenue": round(float(pred["yhat"].sum()), 2)}}