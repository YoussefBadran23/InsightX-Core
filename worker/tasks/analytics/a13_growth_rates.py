"""A13 — Period Growth Rates.

Computes month-over-month, quarter-over-quarter, and year-over-year growth on
revenue, orders, and AOV. Surfaces the best/worst growth periods, the overall
compound monthly growth rate (CMGR), and a 3-month rolling-average smoothed
trend so spiky raw growth doesn't fool the eye.

Headline definitions
--------------------
- **MoM growth %**: (this_month - last_month) / last_month × 100
- **YoY growth %**: (this_month - same_month_last_year) / same_month_last_year × 100
- **QoQ growth %**: like MoM but for calendar quarters
- **CMGR**: ((last / first) ^ (1 / n_months_minus_1)) - 1

CMGR is the geometric mean — what monthly growth rate would carry you from the
first month's revenue to the last month's revenue if growth had been steady.
For a dataset with 24 months and 50% total revenue growth, CMGR ≈ 1.7%/mo.

Required columns:  order_date, total_amount
Optional columns:  net_amount, customer_id, order_id

Output schema::

    {
      "summary": {
        "n_months":    int,
        "first_month": "YYYY-MM",
        "last_month":  "YYYY-MM",
        "total_revenue": float,
        "first_month_revenue": float,
        "last_month_revenue":  float,
        "total_growth_pct":  float,
        "cmgr_pct":          float,    # compound monthly growth rate
        "trend_label":       "growing"|"stable"|"shrinking",
        "best_mom_period":   {"period": str, "growth_pct": float},
        "worst_mom_period":  {"period": str, "growth_pct": float},
        "yoy_available":     bool      # only true with ≥13 months of data
      },
      "monthly":   [{"period": "YYYY-MM", "revenue": float, "orders": int,
                     "aov": float, "mom_pct": float|null, "yoy_pct": float|null,
                     "rolling_3mo_revenue": float}],
      "quarterly": [{"period": "YYYY-Qn", "revenue": float, "orders": int,
                     "aov": float, "qoq_pct": float|null}],
      "yoy_summary": {"current_year_revenue": float, "prior_year_revenue": float,
                      "yoy_pct": float} | null,
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


def _pct_change(curr: float, prev: float) -> float | None:
    """Safe percentage change. Returns None when prev is zero (undefined)."""
    if prev is None or prev == 0:
        return None
    return round((curr - prev) / prev * 100, 2)


@register(
    key="A13_growth_rates",
    analysis_type="revenue",
    required_cols=["order_date", "total_amount"],
    optional_cols=["net_amount", "customer_id", "order_id"],
    description="MoM / QoQ / YoY growth rates with CMGR and rolling smoothing.",
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
                "n_months": 0, "first_month": None, "last_month": None,
                "total_revenue": 0.0, "first_month_revenue": 0.0,
                "last_month_revenue": 0.0, "total_growth_pct": 0.0,
                "cmgr_pct": 0.0, "trend_label": "stable",
                "best_mom_period": None, "worst_mom_period": None,
                "yoy_available": False,
            },
            "monthly": [], "quarterly": [], "yoy_summary": None,
            "warning": "no rows with both order_date and revenue after coercion",
        }

    df["_period_m"] = df["order_date"].dt.to_period("M")
    df["_period_q"] = df["order_date"].dt.to_period("Q")

    # ── Monthly aggregation ─────────────────────────────────────────────────
    monthly = (
        df.groupby("_period_m")
          .agg(revenue=("_revenue", "sum"), orders=("_revenue", "count"))
          .reset_index().sort_values("_period_m")
    )
    monthly["aov"] = (monthly["revenue"] / monthly["orders"]).round(2)

    # MoM with shift(1).
    monthly["mom_pct"] = (
        (monthly["revenue"] - monthly["revenue"].shift(1))
        / monthly["revenue"].shift(1) * 100
    ).round(2)

    # YoY with shift(12) — only meaningful when we have full year-over-year coverage.
    yoy_available = len(monthly) >= 13
    if yoy_available:
        monthly["yoy_pct"] = (
            (monthly["revenue"] - monthly["revenue"].shift(12))
            / monthly["revenue"].shift(12) * 100
        ).round(2)
    else:
        monthly["yoy_pct"] = pd.NA

    # 3-month rolling average to smooth spiky periods.
    monthly["rolling_3mo_revenue"] = (
        monthly["revenue"].rolling(window=3, min_periods=1).mean().round(2)
    )

    # ── Quarterly aggregation ───────────────────────────────────────────────
    quarterly = (
        df.groupby("_period_q")
          .agg(revenue=("_revenue", "sum"), orders=("_revenue", "count"))
          .reset_index().sort_values("_period_q")
    )
    quarterly["aov"] = (quarterly["revenue"] / quarterly["orders"]).round(2)
    quarterly["qoq_pct"] = (
        (quarterly["revenue"] - quarterly["revenue"].shift(1))
        / quarterly["revenue"].shift(1) * 100
    ).round(2)

    # ── Headline metrics ────────────────────────────────────────────────────
    n_months = int(len(monthly))
    first_rev = float(monthly["revenue"].iloc[0])
    last_rev = float(monthly["revenue"].iloc[-1])
    total_rev = float(monthly["revenue"].sum())

    # CMGR = (last / first) ^ (1 / (n - 1)) - 1.
    if n_months >= 2 and first_rev > 0:
        cmgr = (last_rev / first_rev) ** (1.0 / (n_months - 1)) - 1
        cmgr_pct = round(cmgr * 100, 3)
    else:
        cmgr_pct = 0.0

    total_growth = (last_rev - first_rev) / first_rev * 100 if first_rev > 0 else 0.0

    if cmgr_pct > 1.0:
        trend_label = "growing"
    elif cmgr_pct < -1.0:
        trend_label = "shrinking"
    else:
        trend_label = "stable"

    # ── Best / worst MoM ────────────────────────────────────────────────────
    valid_mom = monthly.dropna(subset=["mom_pct"])
    best_mom = worst_mom = None
    if not valid_mom.empty:
        b = valid_mom.loc[valid_mom["mom_pct"].idxmax()]
        w = valid_mom.loc[valid_mom["mom_pct"].idxmin()]
        best_mom = {"period": str(b["_period_m"]), "growth_pct": float(b["mom_pct"])}
        worst_mom = {"period": str(w["_period_m"]), "growth_pct": float(w["mom_pct"])}

    # ── Year-over-year summary (last 12 months vs prior 12) ─────────────────
    yoy_summary = None
    if n_months >= 13:
        recent_year = monthly.tail(12)
        prior_year = monthly.iloc[-24:-12] if n_months >= 24 else monthly.head(n_months - 12)
        recent_rev = float(recent_year["revenue"].sum())
        prior_rev = float(prior_year["revenue"].sum())
        yoy_summary = {
            "current_year_revenue": round(recent_rev, 2),
            "prior_year_revenue": round(prior_rev, 2),
            "yoy_pct": _pct_change(recent_rev, prior_rev) or 0.0,
        }

    # ── Format records ──────────────────────────────────────────────────────
    monthly_records = []
    for r in monthly.to_dict("records"):
        rec = {
            "period": str(r["_period_m"]),
            "revenue": round(float(r["revenue"]), 2),
            "orders": int(r["orders"]),
            "aov": float(r["aov"]),
            "rolling_3mo_revenue": float(r["rolling_3mo_revenue"]),
        }
        rec["mom_pct"] = float(r["mom_pct"]) if pd.notna(r["mom_pct"]) else None
        rec["yoy_pct"] = float(r["yoy_pct"]) if pd.notna(r["yoy_pct"]) else None
        monthly_records.append(rec)

    quarterly_records = []
    for r in quarterly.to_dict("records"):
        rec = {
            "period": str(r["_period_q"]),
            "revenue": round(float(r["revenue"]), 2),
            "orders": int(r["orders"]),
            "aov": float(r["aov"]),
            "qoq_pct": float(r["qoq_pct"]) if pd.notna(r["qoq_pct"]) else None,
        }
        quarterly_records.append(rec)

    return {
        "summary": {
            "n_months": n_months,
            "first_month": str(monthly["_period_m"].iloc[0]),
            "last_month": str(monthly["_period_m"].iloc[-1]),
            "total_revenue": round(total_rev, 2),
            "first_month_revenue": round(first_rev, 2),
            "last_month_revenue": round(last_rev, 2),
            "total_growth_pct": round(total_growth, 2),
            "cmgr_pct": cmgr_pct,
            "trend_label": trend_label,
            "best_mom_period": best_mom,
            "worst_mom_period": worst_mom,
            "yoy_available": yoy_available,
        },
        "monthly": monthly_records,
        "quarterly": quarterly_records,
        "yoy_summary": yoy_summary,
        "warning": None,
    }
