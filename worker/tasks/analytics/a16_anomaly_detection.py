"""A16 — Anomaly Detection on Daily Revenue.

Surfaces days where revenue (and optionally order count) deviated unusually
far from recent context. Two methods combined:

1. **Rolling Z-score (30-day window)** — primary signal. For each day:

       z = (actual - rolling_mean_excluding_self) / rolling_std

   We exclude the day itself from its own rolling stats (otherwise a true
   spike masks itself by inflating the mean and stdev). |z| ≥ 3.0 flags an
   anomaly. The rolling window adapts to seasonality: a day that's "normal
   for that week of June" but spiking in October will still trigger.

2. **IQR cross-check** — secondary signal. Days outside
   [Q1 - 1.5×IQR, Q3 + 1.5×IQR] across the full series are also flagged.
   Catches dataset-wide outliers that rolling Z misses (e.g. a day in month 1
   that has no rolling history yet).

The output emits anomalies ordered by |z| descending so the dashboard can
show the most surprising days first.

Why not Isolation Forest / ARIMA-residual?
------------------------------------------
Both work but require sklearn / statsmodels at scale. Rolling Z + IQR cover
~95% of the "wow look at that day" signal humans care about, with two
fewer dependencies. If a more sophisticated method becomes warranted, we
can swap the engine here without touching the API.

Required columns:  order_date, total_amount
Optional columns:  net_amount, order_id

Output schema::

    {
      "summary": {
        "n_days_analyzed":     int,
        "n_anomalies":         int,
        "n_high_anomalies":    int,    # spikes
        "n_low_anomalies":     int,    # drops
        "anomaly_rate_pct":    float,
        "most_extreme":        {"date": str, "revenue": float, "z_score": float,
                                "deviation_pct": float, "type": "high"|"low"} | null,
        "method":              "rolling_zscore_30d + iqr_cross_check",
        "z_threshold":         float,
        "iqr_multiplier":      float
      },
      "anomalies": [
        {"date": str, "revenue": float, "orders": int,
         "expected_revenue": float, "deviation_pct": float,
         "z_score": float, "type": "high"|"low",
         "flagged_by": ["zscore"|"iqr", ...]}
      ],
      "monthly_anomaly_counts": [
        {"period": "YYYY-MM", "n_high": int, "n_low": int, "total_days": int}
      ],
      "iqr_bounds": {"lower": float, "upper": float, "q1": float, "q3": float},
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


Z_THRESHOLD = 3.0       # |z| ≥ 3 → flag
IQR_MULTIPLIER = 1.5    # Tukey fences
ROLLING_WINDOW = 30     # days
TOP_N_ANOMALIES = 30    # cap output payload


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """Z-score using rolling stats that EXCLUDE the current value.

    Without exclusion, a single big spike inflates its own rolling mean and
    stdev, masking itself. We compute (actual - mean_excl) / std_excl using
    the leave-one-out trick on the window's mean and standard deviation.
    """
    n = len(series)
    if n < window:
        # Not enough history — return zeros so all points pass.
        return pd.Series(np.zeros(n), index=series.index)

    rolling_sum = series.rolling(window=window, min_periods=window).sum()
    rolling_sumsq = (series ** 2).rolling(window=window, min_periods=window).sum()

    # Mean excluding current point: (sum - x) / (n - 1)
    mean_excl = (rolling_sum - series) / (window - 1)
    # Variance excluding current point. Use the standard "online variance"
    # adjustment: take the population variance of the window minus current
    # point's contribution, then re-divide by (window - 1 - 1).
    var_window = (rolling_sumsq - rolling_sum ** 2 / window) / window
    # Bessel-correct toward leave-one-out variance.
    var_excl = var_window * window / (window - 1)
    var_excl -= ((series - mean_excl) ** 2) / (window - 1)
    var_excl = var_excl.clip(lower=0)
    std_excl = np.sqrt(var_excl)

    z = (series - mean_excl) / std_excl.replace(0, np.nan)
    return z.fillna(0.0)


@register(
    key="A16_anomaly_detection",
    analysis_type="revenue",
    required_cols=["order_date", "total_amount"],
    optional_cols=["net_amount", "order_id"],
    description="Daily revenue anomaly detection (rolling Z-score + IQR fences).",
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
        return _empty_result("no rows with both order_date and revenue after coercion")

    # ── Daily aggregation (gap-filled with zeros) ───────────────────────────
    df["_date"] = df["order_date"].dt.normalize()
    daily = (
        df.groupby("_date")
          .agg(revenue=(revenue_col, "sum"), orders=(revenue_col, "count"))
          .reset_index().sort_values("_date")
    )
    full_idx = pd.date_range(daily["_date"].min(), daily["_date"].max(), freq="D")
    daily = daily.set_index("_date").reindex(full_idx, fill_value=0).reset_index()
    daily = daily.rename(columns={"index": "date"})

    n_days = int(len(daily))
    if n_days < 7:
        return _empty_result(
            f"only {n_days} days of data — anomaly detection needs ≥7 days for any signal"
        )

    # ── Rolling Z-score on revenue ──────────────────────────────────────────
    z_window = min(ROLLING_WINDOW, max(7, n_days // 4))
    daily["z_score"] = _rolling_zscore(daily["revenue"], window=z_window).round(3)
    # Expected = the rolling mean (without the current point) — used for
    # display ("you saw X, expected Y").
    rolling_sum = daily["revenue"].rolling(window=z_window, min_periods=z_window).sum()
    daily["expected"] = ((rolling_sum - daily["revenue"]) / (z_window - 1)).fillna(
        daily["revenue"].rolling(window=z_window, min_periods=1).mean()
    )

    # ── IQR fences (full-series, secondary check) ───────────────────────────
    q1 = float(daily["revenue"].quantile(0.25))
    q3 = float(daily["revenue"].quantile(0.75))
    iqr = q3 - q1
    iqr_lower = q1 - IQR_MULTIPLIER * iqr
    iqr_upper = q3 + IQR_MULTIPLIER * iqr

    daily["_iqr_outlier"] = (daily["revenue"] < iqr_lower) | (daily["revenue"] > iqr_upper)
    daily["_z_outlier"] = daily["z_score"].abs() >= Z_THRESHOLD

    # An anomaly is anything flagged by either method.
    daily["_is_anomaly"] = daily["_z_outlier"] | daily["_iqr_outlier"]
    daily["_type"] = np.where(
        (daily["z_score"] > 0) | (daily["revenue"] > q3),
        "high", "low",
    )
    # Override type for clear IQR-only cases
    high_iqr = daily["revenue"] > iqr_upper
    low_iqr = daily["revenue"] < iqr_lower
    daily.loc[high_iqr, "_type"] = "high"
    daily.loc[low_iqr, "_type"] = "low"

    anomalies_df = daily[daily["_is_anomaly"]].copy()
    anomalies_df["_abs_z"] = anomalies_df["z_score"].abs()
    anomalies_df = anomalies_df.sort_values("_abs_z", ascending=False)

    n_anom = int(len(anomalies_df))
    n_high = int((anomalies_df["_type"] == "high").sum())
    n_low = int((anomalies_df["_type"] == "low").sum())

    most_extreme = None
    if n_anom > 0:
        top = anomalies_df.iloc[0]
        exp = float(top["expected"]) or 1.0
        deviation_pct = (float(top["revenue"]) - exp) / abs(exp) * 100 if exp != 0 else 0.0
        most_extreme = {
            "date": top["date"].strftime("%Y-%m-%d"),
            "revenue": round(float(top["revenue"]), 2),
            "z_score": round(float(top["z_score"]), 3),
            "deviation_pct": round(deviation_pct, 2),
            "type": str(top["_type"]),
        }

    # ── Top-N anomaly records ───────────────────────────────────────────────
    anomalies_out: list[dict[str, Any]] = []
    for r in anomalies_df.head(TOP_N_ANOMALIES).to_dict("records"):
        exp = float(r["expected"])
        if exp == 0:
            dev = 100.0 if r["revenue"] > 0 else 0.0
        else:
            dev = (float(r["revenue"]) - exp) / abs(exp) * 100
        flagged_by: list[str] = []
        if r["_z_outlier"]:
            flagged_by.append("zscore")
        if r["_iqr_outlier"]:
            flagged_by.append("iqr")
        anomalies_out.append({
            "date": r["date"].strftime("%Y-%m-%d"),
            "revenue": round(float(r["revenue"]), 2),
            "orders": int(r["orders"]),
            "expected_revenue": round(exp, 2),
            "deviation_pct": round(dev, 2),
            "z_score": round(float(r["z_score"]), 3),
            "type": str(r["_type"]),
            "flagged_by": flagged_by,
        })

    # ── Monthly anomaly counts ──────────────────────────────────────────────
    daily["_period"] = daily["date"].dt.to_period("M").astype(str)
    monthly = (
        daily.groupby("_period")
             .agg(total_days=("date", "count"),
                  n_high=("_is_anomaly", lambda s: int(((s) & (daily.loc[s.index, "_type"] == "high")).sum())),
                  n_low=("_is_anomaly", lambda s: int(((s) & (daily.loc[s.index, "_type"] == "low")).sum())))
             .reset_index().rename(columns={"_period": "period"})
             .sort_values("period")
    )
    monthly_records = [
        {"period": str(r["period"]),
         "n_high": int(r["n_high"]),
         "n_low": int(r["n_low"]),
         "total_days": int(r["total_days"])}
        for r in monthly.to_dict("records")
    ]

    return {
        "summary": {
            "n_days_analyzed": n_days,
            "n_anomalies": n_anom,
            "n_high_anomalies": n_high,
            "n_low_anomalies": n_low,
            "anomaly_rate_pct": round(n_anom / n_days * 100, 2),
            "most_extreme": most_extreme,
            "method": f"rolling_zscore_{z_window}d + iqr_cross_check",
            "z_threshold": Z_THRESHOLD,
            "iqr_multiplier": IQR_MULTIPLIER,
        },
        "anomalies": anomalies_out,
        "monthly_anomaly_counts": monthly_records,
        "iqr_bounds": {
            "lower": round(iqr_lower, 2),
            "upper": round(iqr_upper, 2),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
        },
        "warning": None,
    }


def _empty_result(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_days_analyzed": 0, "n_anomalies": 0,
            "n_high_anomalies": 0, "n_low_anomalies": 0,
            "anomaly_rate_pct": 0.0, "most_extreme": None,
            "method": f"rolling_zscore_{ROLLING_WINDOW}d + iqr_cross_check",
            "z_threshold": Z_THRESHOLD,
            "iqr_multiplier": IQR_MULTIPLIER,
        },
        "anomalies": [], "monthly_anomaly_counts": [],
        "iqr_bounds": {"lower": 0.0, "upper": 0.0, "q1": 0.0, "q3": 0.0},
        "warning": warning,
    }
