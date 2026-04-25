"""A22 — Fulfillment SLA Analysis.

Analyzes delivery time distribution and SLA compliance.
"""

import pandas as pd
import numpy as np
from ._base import analytics_task, has_col


@analytics_task("A22_fulfillment_sla", "fulfillment")
def run_fulfillment_sla(df, session, job_id):
    if not has_col(df, "delivery_days"):
        return {"summary": "No delivery_days column", "sla_compliance": {}}

    df = df.copy()
    df["delivery_days"] = pd.to_numeric(df["delivery_days"], errors="coerce")
    df = df.dropna(subset=["delivery_days"])
    df["delivery_days"] = df["delivery_days"].astype(int)

    if len(df) == 0:
        return {"summary": "No valid delivery data", "sla_compliance": {}}

    # SLA thresholds
    sla_thresholds = {"3_day": 3, "5_day": 5, "7_day": 7, "14_day": 14}
    sla_compliance = {}
    for name, days in sla_thresholds.items():
        met = int((df["delivery_days"] <= days).sum())
        sla_compliance[name] = {
            "threshold_days": days,
            "met": met,
            "pct": round(met / len(df) * 100, 2),
        }

    # Distribution stats
    stats = {
        "mean": round(float(df["delivery_days"].mean()), 1),
        "median": float(df["delivery_days"].median()),
        "p90": float(df["delivery_days"].quantile(0.90)),
        "p95": float(df["delivery_days"].quantile(0.95)),
        "min": int(df["delivery_days"].min()),
        "max": int(df["delivery_days"].max()),
    }

    # Histogram
    bins = list(range(0, int(df["delivery_days"].max()) + 3, 1))
    if len(bins) > 30:
        bins = list(np.linspace(0, df["delivery_days"].max(), 20, dtype=int))
    hist_counts, hist_edges = np.histogram(df["delivery_days"], bins=bins)
    histogram = [
        {"days": int(hist_edges[i]), "count": int(hist_counts[i])}
        for i in range(len(hist_counts))
    ]

    result = {
        "sla_compliance": sla_compliance,
        "stats": stats,
        "histogram": histogram,
        "total_orders": len(df),
    }

    # By region
    if has_col(df, "region"):
        region = df.groupby("region")["delivery_days"].agg(
            ["mean", "median", "count"]
        ).round(1).reset_index()
        region.columns = ["region", "avg_days", "median_days", "orders"]
        result["by_region"] = region.to_dict("records")

    return result
