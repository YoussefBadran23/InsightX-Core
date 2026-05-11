"""A08 — Average Order Value (AOV) Trends.

Tracks how AOV evolves over time and surfaces the patterns hiding inside it:
day-of-week effects, monthly seasonality, recent vs prior period drift, and
(when customer_id is available) the new-vs-returning AOV gap.

Trend detection
---------------
We fit a linear regression of monthly AOV against month index to estimate the
month-over-month slope, then express it as a % of the overall mean. Labels:

    >  +0.5% per month  → "growing"
    -0.5% .. +0.5%       → "stable"
    <  -0.5% per month  → "shrinking"

This is intentionally a coarse signal; A13 (growth rates) and A15 (Prophet
forecast) drill deeper. A08 is the at-a-glance "is AOV moving?" view.

Required columns:  order_date, total_amount
Optional columns:  net_amount, customer_id

Output schema::

    {
      "summary": {
        "overall_aov":      float,
        "n_orders":         int,
        "n_days":           int,
        "date_range":       {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
        "recent_30d_aov":   float,
        "prior_30d_aov":    float,
        "aov_change_pct":   float,
        "trend":            "growing"|"stable"|"shrinking",
        "monthly_slope_pct": float
      },
      "by_period": {"daily": [...], "weekly": [...], "monthly": [...]},
      "by_dow":            [{"day": str, "day_idx": int, "aov": float, "orders": int}],
      "by_month_of_year":  [{"month": str, "month_idx": int, "aov": float, "orders": int}],
      "new_vs_returning":  {"new": {...}, "returning": {...}, "lift_pct": float} | null,
      "top_aov_days":      [{"date": str, "aov": float, "orders": int, "revenue": float}],
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _aov_records(grouped: pd.DataFrame, key_col: str) -> list[dict[str, Any]]:
    """Convert a grouped (key, revenue, orders) frame into AOV records."""
    out = []
    for r in grouped.to_dict("records"):
        orders = int(r["orders"])
        rev = float(r["revenue"])
        aov = round(rev / orders, 2) if orders > 0 else 0.0
        out.append({
            key_col: str(r[key_col]) if not isinstance(r[key_col], (int, float)) else r[key_col],
            "aov": aov,
            "orders": orders,
            "revenue": round(rev, 2),
        })
    return out


@register(
    key="A08_aov_trends",
    analysis_type="revenue",
    required_cols=["order_date", "total_amount"],
    optional_cols=["net_amount", "customer_id"],
    description="Average Order Value trends with seasonality and new-vs-returning split.",
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
    df["_revenue"] = df[revenue_col]

    if df.empty:
        return {
            "summary": {
                "overall_aov": 0.0, "n_orders": 0, "n_days": 0,
                "date_range": {"start": None, "end": None},
                "recent_30d_aov": 0.0, "prior_30d_aov": 0.0,
                "aov_change_pct": 0.0, "trend": "stable", "monthly_slope_pct": 0.0,
            },
            "by_period": {"daily": [], "weekly": [], "monthly": []},
            "by_dow": [], "by_month_of_year": [],
            "new_vs_returning": None, "top_aov_days": [],
            "warning": "no rows with both order_date and revenue after coercion",
        }

    n_orders = int(len(df))
    total_rev = float(df["_revenue"].sum())
    overall_aov = round(total_rev / n_orders, 2)
    date_min, date_max = df["order_date"].min(), df["order_date"].max()
    n_days = int((date_max - date_min).days + 1)

    # ── Time-series aggregates ──────────────────────────────────────────────
    df["_date"] = df["order_date"].dt.date
    daily = (
        df.groupby("_date")
          .agg(revenue=("_revenue", "sum"), orders=("_revenue", "count"))
          .reset_index().rename(columns={"_date": "date"})
          .sort_values("date")
    )
    weekly = (
        df.groupby(df["order_date"].dt.to_period("W"))
          .agg(revenue=("_revenue", "sum"), orders=("_revenue", "count"))
          .reset_index().rename(columns={"order_date": "period"})
    )
    weekly["period"] = weekly["period"].astype(str)
    monthly = (
        df.groupby(df["order_date"].dt.to_period("M"))
          .agg(revenue=("_revenue", "sum"), orders=("_revenue", "count"))
          .reset_index().rename(columns={"order_date": "period"})
    )
    monthly["period"] = monthly["period"].astype(str)

    daily_records = []
    for r in daily.to_dict("records"):
        orders = int(r["orders"])
        aov = round(r["revenue"] / orders, 2) if orders > 0 else 0.0
        daily_records.append({
            "date": str(r["date"]),
            "aov": aov,
            "orders": orders,
            "revenue": round(float(r["revenue"]), 2),
        })

    weekly_records = _aov_records(weekly, "period")
    monthly_records = _aov_records(monthly, "period")

    # ── Recent vs prior 30-day comparison ───────────────────────────────────
    recent_cutoff = date_max - pd.Timedelta(days=30)
    prior_start = date_max - pd.Timedelta(days=60)
    recent = df[df["order_date"] > recent_cutoff]
    prior = df[(df["order_date"] > prior_start) & (df["order_date"] <= recent_cutoff)]
    recent_aov = (
        round(float(recent["_revenue"].sum()) / len(recent), 2)
        if len(recent) > 0 else 0.0
    )
    prior_aov = (
        round(float(prior["_revenue"].sum()) / len(prior), 2)
        if len(prior) > 0 else 0.0
    )
    if prior_aov > 0:
        change_pct = round((recent_aov - prior_aov) / prior_aov * 100, 2)
    else:
        change_pct = 0.0

    # ── Linear trend on monthly AOV ─────────────────────────────────────────
    monthly_slope_pct = 0.0
    if len(monthly_records) >= 3:
        ys = np.array([r["aov"] for r in monthly_records], dtype=float)
        xs = np.arange(len(ys), dtype=float)
        # numpy returns (slope, intercept). polyfit handles edge cases.
        slope, _ = np.polyfit(xs, ys, 1)
        if overall_aov > 0:
            monthly_slope_pct = round(float(slope) / overall_aov * 100, 3)

    if monthly_slope_pct > 0.5:
        trend = "growing"
    elif monthly_slope_pct < -0.5:
        trend = "shrinking"
    else:
        trend = "stable"

    # ── Day-of-week pattern ─────────────────────────────────────────────────
    df["_dow"] = df["order_date"].dt.dayofweek  # 0 = Mon
    dow_grouped = (
        df.groupby("_dow")
          .agg(revenue=("_revenue", "sum"), orders=("_revenue", "count"))
          .reset_index().rename(columns={"_dow": "day_idx"})
    )
    by_dow = []
    for r in dow_grouped.to_dict("records"):
        orders = int(r["orders"])
        aov = round(r["revenue"] / orders, 2) if orders > 0 else 0.0
        by_dow.append({
            "day": DOW_NAMES[int(r["day_idx"])],
            "day_idx": int(r["day_idx"]),
            "aov": aov,
            "orders": orders,
        })

    # ── Month-of-year (seasonality) ─────────────────────────────────────────
    df["_month"] = df["order_date"].dt.month  # 1-12
    moy_grouped = (
        df.groupby("_month")
          .agg(revenue=("_revenue", "sum"), orders=("_revenue", "count"))
          .reset_index().rename(columns={"_month": "month_idx"})
    )
    by_moy = []
    for r in moy_grouped.to_dict("records"):
        orders = int(r["orders"])
        aov = round(r["revenue"] / orders, 2) if orders > 0 else 0.0
        by_moy.append({
            "month": MONTH_NAMES[int(r["month_idx"]) - 1],
            "month_idx": int(r["month_idx"]),
            "aov": aov,
            "orders": orders,
        })

    # ── New vs returning AOV (if customer_id available) ─────────────────────
    new_vs_returning = None
    if has_col(df, "customer_id"):
        df["customer_id"] = df["customer_id"].astype(str)
        df = df.sort_values(["customer_id", "order_date"])
        df["_order_rank"] = df.groupby("customer_id").cumcount()
        new_orders = df[df["_order_rank"] == 0]
        ret_orders = df[df["_order_rank"] > 0]

        def _bucket(sub: pd.DataFrame) -> dict[str, Any]:
            n = int(len(sub))
            rev = float(sub["_revenue"].sum())
            aov = round(rev / n, 2) if n > 0 else 0.0
            return {"orders": n, "revenue": round(rev, 2), "aov": aov}

        new_b = _bucket(new_orders)
        ret_b = _bucket(ret_orders)
        if new_b["aov"] > 0 and ret_b["orders"] > 0:
            lift_pct = round((ret_b["aov"] - new_b["aov"]) / new_b["aov"] * 100, 2)
        else:
            lift_pct = 0.0
        new_vs_returning = {
            "new": new_b, "returning": ret_b, "lift_pct": lift_pct,
        }

    # ── Top 10 AOV days (min 5 orders to dampen noise) ──────────────────────
    eligible_days = daily[daily["orders"] >= 5].copy()
    eligible_days["aov"] = (eligible_days["revenue"] / eligible_days["orders"]).round(2)
    eligible_days = eligible_days.nlargest(10, "aov")
    top_aov_days = [
        {"date": str(r["date"]), "aov": float(r["aov"]),
         "orders": int(r["orders"]), "revenue": round(float(r["revenue"]), 2)}
        for r in eligible_days.to_dict("records")
    ]

    return {
        "summary": {
            "overall_aov": overall_aov,
            "n_orders": n_orders,
            "n_days": n_days,
            "date_range": {
                "start": date_min.date().isoformat(),
                "end": date_max.date().isoformat(),
            },
            "recent_30d_aov": recent_aov,
            "prior_30d_aov": prior_aov,
            "aov_change_pct": change_pct,
            "trend": trend,
            "monthly_slope_pct": monthly_slope_pct,
        },
        "by_period": {
            "daily": daily_records,
            "weekly": weekly_records,
            "monthly": monthly_records,
        },
        "by_dow": by_dow,
        "by_month_of_year": by_moy,
        "new_vs_returning": new_vs_returning,
        "top_aov_days": top_aov_days,
        "warning": None,
    }
