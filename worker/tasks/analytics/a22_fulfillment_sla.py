"""A22 — Fulfillment SLA Analysis (Optimized & Complete)."""
import pandas as pd
import numpy as np
from ._base import analytics_task, has_col

COLS = ["delivery_days", "region", "status"]

@analytics_task("A22_fulfillment_sla", "fulfillment", required_cols=COLS)
def run_fulfillment_sla(df, session, job_id):
    df["delivery_days"] = pd.to_numeric(df["delivery_days"], errors="coerce").dropna()
    if df.empty: return {"summary": "No delivery data"}

    # SLA Thresholds
    met_3d = (df.delivery_days <= 3).mean() * 100
    met_7d = (df.delivery_days <= 7).mean() * 100

    # Regional Performance
    reg_stats = df.groupby("region")["delivery_days"].agg(["mean", "median", "count"]).round(1).reset_index()

    return {
        "sla_performance": {"3_day_pct": round(met_3d, 2), "7_day_pct": round(met_7d, 2)},
        "avg_delivery_days": round(float(df.delivery_days.mean()), 1),
        "regional_stats": reg_stats.to_dict("records"),
        "max_delay": int(df.delivery_days.max())
    }