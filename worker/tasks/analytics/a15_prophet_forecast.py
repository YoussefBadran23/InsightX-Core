"""A15 — Revenue Forecasting (Prophet + statsmodels fallback).

Fits a daily-revenue forecast model and emits 30/60/90/180-day forward
predictions with 80% confidence intervals plus a 30-day holdout backtest.

Engine selection
----------------
Prophet is the preferred engine, but it requires a built CmdStan binary
(~500MB) which dev / CI environments often don't have. We try Prophet first
and fall back transparently to statsmodels' Holt-Winters Exponential
Smoothing — same daily-grain forecast shape, just less expressive about
trend changepoints.

The chosen engine is reported in `summary.model_engine` so the dashboard can
show which model produced the numbers.

Numpy 2.x note
--------------
Prophet 1.1.5 still references `np.float_` (removed in numpy 2.0). We patch
it before the import. Drop the shim once Prophet ships a numpy-2 release.

Required columns:  order_date, total_amount
Optional columns:  net_amount

Output schema is identical for both engines (see _empty_result for keys).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

# Apply numpy-2 shim BEFORE importing Prophet. Order matters.
if not hasattr(np, "float_"):
    np.float_ = np.float64  # type: ignore[attr-defined]

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_money


QUESTION = "How much revenue should I expect over the next 30 days?"


logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

MIN_DAYS_FOR_FIT = 14
MIN_DAYS_FOR_YEARLY = 365
MIN_DAYS_FOR_BACKTEST = 60
HOLDOUT_DAYS = 30
FORECAST_HORIZON = 180


# ── Engine probing ──────────────────────────────────────────────────────────

def _try_prophet() -> Optional[str]:
    """Return the engine string if Prophet is usable, else None.

    We don't just check `import prophet` — many environments have the package
    installed but no CmdStan binary, which fails at fit time with an opaque
    'stan_backend' error. Probing here means we fall back early.
    """
    try:
        import cmdstanpy
        cmdstanpy.cmdstan_path()  # raises if no built binary
        from prophet import Prophet  # noqa: F401
        import prophet
        return f"prophet {prophet.__version__}"
    except Exception:
        return None


def _try_statsmodels() -> Optional[str]:
    try:
        import statsmodels
        from statsmodels.tsa.holtwinters import ExponentialSmoothing  # noqa: F401
        return f"statsmodels {statsmodels.__version__} (Holt-Winters)"
    except Exception:
        return None


# ── Daily aggregation ───────────────────────────────────────────────────────

def _build_daily(df: pd.DataFrame, revenue_col: str) -> pd.DataFrame:
    df["_date"] = df["order_date"].dt.normalize()
    daily = (
        df.groupby("_date")[revenue_col].sum()
          .reset_index().rename(columns={"_date": "ds", revenue_col: "y"})
          .sort_values("ds")
    )
    full_idx = pd.date_range(start=daily["ds"].min(), end=daily["ds"].max(), freq="D")
    daily = daily.set_index("ds").reindex(full_idx, fill_value=0.0).reset_index()
    daily = daily.rename(columns={"index": "ds"})
    return daily


# ── Prophet path ────────────────────────────────────────────────────────────

def _forecast_prophet(daily: pd.DataFrame, enable_yearly: bool, horizon: int):
    from prophet import Prophet
    model = Prophet(
        weekly_seasonality=True,
        yearly_seasonality=enable_yearly,
        daily_seasonality=False,
        interval_width=0.80,
        changepoint_prior_scale=0.05,
        seasonality_mode="additive",
    )
    model.fit(daily)
    future = model.make_future_dataframe(periods=horizon, include_history=True)
    fc = model.predict(future)
    return fc, ("yhat", "yhat_lower", "yhat_upper", "trend", "weekly", "yearly" if enable_yearly else None)


# ── statsmodels fallback ────────────────────────────────────────────────────

def _forecast_statsmodels(daily: pd.DataFrame, enable_yearly: bool, horizon: int):
    """Holt-Winters with weekly (and optionally yearly) seasonal periods.

    Output mimics Prophet's columns so downstream code is engine-agnostic:
    we synthesize `yhat`, `yhat_lower`, `yhat_upper`, plus a piecewise-linear
    `trend` and a `weekly` seasonality vector. `yearly` is not produced — the
    Holt-Winters model can only carry one seasonal period at a time.
    """
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    series = daily["y"].astype(float).values
    n = len(series)

    # Holt-Winters with 7-day seasonal period (weekly cycle is the dominant
    # signal in daily e-commerce data; yearly seasonality is captured by the
    # underlying additive trend).
    model = ExponentialSmoothing(
        series,
        trend="add",
        seasonal="add",
        seasonal_periods=7,
        initialization_method="estimated",
    ).fit()

    in_sample = model.fittedvalues
    fc_values = model.forecast(horizon)

    # Approximate prediction interval via residual stdev × 1.282 (z for 80% CI).
    resid = series - in_sample
    sigma = float(np.nanstd(resid))
    z = 1.282

    # Build the combined frame matching Prophet's "history + future" shape.
    all_dates = list(daily["ds"]) + [
        daily["ds"].iloc[-1] + pd.Timedelta(days=i + 1) for i in range(horizon)
    ]
    yhat = np.concatenate([in_sample, fc_values])
    out = pd.DataFrame({"ds": all_dates, "yhat": yhat})
    out["yhat_lower"] = out["yhat"] - z * sigma
    out["yhat_upper"] = out["yhat"] + z * sigma

    # Trend = 30-day centered rolling mean of actuals. seasonal_decompose's
    # `extrapolate_trend="freq"` was tried first but produces wildly unstable
    # values at the edges — the centered MA has few data points there, and
    # the linear extrapolation amplifies noise. A rolling mean is a more
    # honest signal of "smoothed level".
    window = min(30, max(7, n // 5))
    trend_in = (
        pd.Series(series)
          .rolling(window=window, min_periods=1, center=True)
          .mean().values
    )
    # Weekly: average residual per day-of-week.
    detrended = series - trend_in
    dow_idx = pd.Series(daily["ds"]).dt.dayofweek.values
    dow_means = pd.Series(detrended).groupby(dow_idx).mean().to_dict()
    weekly_in = np.array([dow_means.get(d, 0.0) for d in dow_idx])

    # Extend trend linearly for the forecast window using the slope from the
    # last `window` days only (avoids being dragged by ancient history).
    if n >= window:
        recent_slope = float((trend_in[-1] - trend_in[-window]) / max(window - 1, 1))
    elif n >= 2:
        recent_slope = float((trend_in[-1] - trend_in[0]) / max(n - 1, 1))
    else:
        recent_slope = 0.0
    trend_future = trend_in[-1] + recent_slope * np.arange(1, horizon + 1)

    # Weekly: replicate the last 7 days' seasonal values forward.
    if len(weekly_in) >= 7:
        last_week = weekly_in[-7:]
        weekly_future = np.tile(last_week, int(np.ceil(horizon / 7)))[:horizon]
    else:
        weekly_future = np.zeros(horizon)

    out["trend"] = np.concatenate([trend_in, trend_future])
    out["weekly"] = np.concatenate([weekly_in, weekly_future])
    # Yearly not supported in this fallback.
    return out, ("yhat", "yhat_lower", "yhat_upper", "trend", "weekly", None)


# ── Core run() ──────────────────────────────────────────────────────────────

@register(
    key="A15_prophet_forecast",
    analysis_type="revenue",
    required_cols=["order_date", "total_amount"],
    optional_cols=["net_amount"],
    description="Daily revenue forecast (Prophet, with statsmodels fallback) + backtest.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])

    revenue_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["order_date", revenue_col])
    df = df[df[revenue_col] >= 0]

    if df.empty:
        return _empty_result("no rows with both order_date and revenue after coercion", "none")

    daily = _build_daily(df, revenue_col)
    n_train = len(daily)

    if n_train < MIN_DAYS_FOR_FIT:
        return _empty_result(
            f"only {n_train} days of data — need ≥{MIN_DAYS_FOR_FIT} for a meaningful fit",
            "none",
        )

    enable_yearly = n_train >= MIN_DAYS_FOR_YEARLY
    first_date = daily["ds"].iloc[0].date()
    last_date = daily["ds"].iloc[-1].date()

    # Pick engine.
    engine_label = _try_prophet() or _try_statsmodels() or "none"
    if engine_label == "none":
        return _empty_result(
            "no forecasting engine available — install Prophet+CmdStan or statsmodels",
            "none",
        )
    use_prophet = engine_label.startswith("prophet")
    forecast_fn = _forecast_prophet if use_prophet else _forecast_statsmodels

    # ── Backtest ────────────────────────────────────────────────────────────
    backtest_mae = None
    backtest_mape = None
    if n_train >= MIN_DAYS_FOR_BACKTEST:
        cutoff = n_train - HOLDOUT_DAYS
        train_bt = daily.iloc[:cutoff].copy()
        test_bt = daily.iloc[cutoff:].copy()
        try:
            fc_bt, _ = forecast_fn(train_bt, enable_yearly=enable_yearly, horizon=HOLDOUT_DAYS)
            future_only = fc_bt[fc_bt["ds"] > train_bt["ds"].max()]
            joined = test_bt.merge(future_only[["ds", "yhat"]], on="ds", how="inner")
            if not joined.empty:
                err = (joined["y"] - joined["yhat"]).abs()
                backtest_mae = round(float(err.mean()), 2)
                nz = joined[joined["y"] > 0]
                if not nz.empty:
                    backtest_mape = round(
                        float((err[nz.index] / nz["y"]).mean() * 100), 2
                    )
        except Exception as e:
            logging.warning(f"A15 backtest failed: {type(e).__name__}: {e}")

    # ── Final fit on full history ───────────────────────────────────────────
    fc, _ = forecast_fn(daily, enable_yearly=enable_yearly, horizon=FORECAST_HORIZON)
    last_ds = daily["ds"].max()
    fc_hist = fc[fc["ds"] <= last_ds].merge(daily, on="ds", how="left")
    fc_future = fc[fc["ds"] > last_ds].copy()

    horizons = [30, 60, 90, 180]
    horizon_totals: dict[int, float] = {}
    for h in horizons:
        sub = fc_future.head(h)
        horizon_totals[h] = round(float(sub["yhat"].clip(lower=0).sum()), 2)

    # ── Trend slope (in-sample only) ────────────────────────────────────────
    # The forecast frame's tail is *extrapolated* trend; including it would
    # exaggerate direction labels. Restrict to the actual training window.
    trend_in_sample = fc.iloc[: len(daily)]["trend"]
    if len(trend_in_sample) >= 2:
        slope_per_day = float(
            (trend_in_sample.iloc[-1] - trend_in_sample.iloc[0])
            / max(len(trend_in_sample) - 1, 1)
        )
        latest_level = float(trend_in_sample.iloc[-1])
        slope_pct = (
            round(slope_per_day / max(abs(latest_level), 1) * 100, 4)
            if latest_level != 0 else 0.0
        )
    else:
        slope_pct = 0.0

    if slope_pct > 0.05:
        trend_label = "growing"
    elif slope_pct < -0.05:
        trend_label = "shrinking"
    else:
        trend_label = "flat"

    # ── Output records ──────────────────────────────────────────────────────
    history_records = [
        {
            "date": r["ds"].strftime("%Y-%m-%d"),
            "actual": round(float(r["y"]), 2) if pd.notna(r.get("y")) else None,
            "fitted": round(float(r["yhat"]), 2),
            "lower": round(float(r["yhat_lower"]), 2),
            "upper": round(float(r["yhat_upper"]), 2),
        }
        for r in fc_hist.to_dict("records")
    ]

    forecast_records = []
    for i, r in enumerate(fc_future.to_dict("records")):
        forecast_records.append({
            "date": r["ds"].strftime("%Y-%m-%d"),
            "yhat": round(float(r["yhat"]), 2),
            "lower": round(float(r["yhat_lower"]), 2),
            "upper": round(float(r["yhat_upper"]), 2),
            "horizon": i + 1,
        })

    trend_step = max(1, len(fc) // 52)
    trend_records = [
        {"date": r["ds"].strftime("%Y-%m-%d"), "value": round(float(r["trend"]), 2)}
        for r in fc.iloc[::trend_step].to_dict("records")
    ]

    weekly_records: list[dict[str, Any]] = []
    if "weekly" in fc.columns:
        # Take any 7 consecutive days from the predicted range so we get all DOWs.
        week_sample = fc.tail(7).copy()
        week_sample["day_idx"] = pd.to_datetime(week_sample["ds"]).dt.dayofweek
        week_sample = week_sample.sort_values("day_idx")
        for r in week_sample.to_dict("records"):
            weekly_records.append({
                "day_idx": int(r["day_idx"]),
                "day": DOW_NAMES[int(r["day_idx"])],
                "value": round(float(r["weekly"]), 2),
            })

    yearly_records = None
    if enable_yearly and use_prophet and "yearly" in fc.columns:
        year_sample = fc[["ds", "yearly"]].copy()
        year_sample["doy"] = pd.to_datetime(year_sample["ds"]).dt.dayofyear
        year_avg = year_sample.groupby("doy")["yearly"].mean().reset_index()
        year_step = max(1, len(year_avg) // 52)
        yearly_records = [
            {"day_of_year": int(r["doy"]), "value": round(float(r["yearly"]), 2)}
            for r in year_avg.iloc[::year_step].to_dict("records")
        ]

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    forecast_30d = horizon_totals.get(30, 0.0)
    forecast_90d = horizon_totals.get(90, 0.0)
    forecast_180d = horizon_totals.get(180, 0.0)

    headline = build_headline(
        value=round(forecast_30d, 2),
        label="projected revenue · next 30 days",
        trend_pct=slope_pct * 30 if slope_pct != 0 else None,
        period=f"{n_train} days of history",
    )

    bullets: list[str] = []
    bullets.append(
        f"Next 30 days: {fmt_money(forecast_30d)} projected · 90d: {fmt_money(forecast_90d)} · "
        f"180d: {fmt_money(forecast_180d)} (80% confidence band)."
    )

    if trend_label == "growing":
        bullets.append(
            f"Underlying trend is growing — slope {slope_pct:+.3f}%/day. "
            f"At this pace, monthly revenue compounds ~{slope_pct * 30:+.1f}%/month."
        )
    elif trend_label == "shrinking":
        bullets.append(
            f"Underlying trend is contracting — slope {slope_pct:+.3f}%/day. "
            f"Find the leak before the forecast catches up to reality."
        )
    else:
        bullets.append(
            f"Underlying trend is flat (slope {slope_pct:+.3f}%/day) — "
            f"forecast leans on weekly seasonality, not growth momentum."
        )

    if backtest_mape is not None:
        if backtest_mape <= 15:
            bullets.append(
                f"Backtest accuracy: ±{backtest_mape:.0f}% (30-day holdout) — "
                f"the forecast is reliable for planning."
            )
        elif backtest_mape <= 30:
            bullets.append(
                f"Backtest accuracy: ±{backtest_mape:.0f}% — usable as a guide, "
                f"but treat ranges, not point values, as truth."
            )
        else:
            bullets.append(
                f"Backtest accuracy: ±{backtest_mape:.0f}% — high variance suggests "
                f"recent shocks; rely on the confidence band, not the line."
            )
    else:
        bullets.append(
            f"Engine: {engine_label} · enable yearly seasonality at 365+ days of data."
        )

    actions = [
        action("Open forecast dashboard", kind="primary",
               deeplink="/dashboard/forecasting", icon="arrow"),
        action("Tune horizon", kind="info",
               deeplink="/dashboard/forecasting?horizon=90", icon="arrow"),
        action("Export forecast CSV", kind="secondary",
               deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary": {
            "n_train_days": int(n_train),
            "first_date": first_date.isoformat(),
            "last_date": last_date.isoformat(),
            "total_revenue_30d_forecast": forecast_30d,
            "total_revenue_60d_forecast": horizon_totals.get(60, 0.0),
            "total_revenue_90d_forecast": forecast_90d,
            "total_revenue_180d_forecast": forecast_180d,
            "trend_label": trend_label,
            "trend_slope_pct_per_day": slope_pct,
            "backtest_mae": backtest_mae,
            "backtest_mape": backtest_mape,
            "model_engine": engine_label,
        },
        "history": history_records,
        "forecast": forecast_records,
        "components": {
            "trend": trend_records,
            "weekly": weekly_records,
            "yearly": yearly_records,
        },
        "warning": None,
    }


def _empty_result(warning: str, engine: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="projected revenue · next 30 days",
                                    period="no data"),
            fallback_bullets=[
                "Not enough order history to forecast yet — need at least "
                f"{MIN_DAYS_FOR_FIT} days of daily data with revenue.",
                "Once you have 14+ days, this card projects 30/60/90/180-day "
                "revenue with an 80% confidence band.",
                "60+ days unlocks a backtest accuracy score so you know "
                "how trustworthy the forecast is.",
            ],
            suggested_actions=[
                action("Upload more order history", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {
            "n_train_days": 0, "first_date": None, "last_date": None,
            "total_revenue_30d_forecast": 0.0,
            "total_revenue_60d_forecast": 0.0,
            "total_revenue_90d_forecast": 0.0,
            "total_revenue_180d_forecast": 0.0,
            "trend_label": "flat", "trend_slope_pct_per_day": 0.0,
            "backtest_mae": None, "backtest_mape": None,
            "model_engine": engine,
        },
        "history": [], "forecast": [],
        "components": {"trend": [], "weekly": [], "yearly": None},
        "warning": warning,
    }
