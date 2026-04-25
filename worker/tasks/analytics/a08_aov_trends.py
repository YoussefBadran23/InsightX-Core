"""A08 — Average Order Value Trends.

AOV over time (daily/monthly), by region, distribution histogram.
"""

import numpy as np
import pandas as pd
from ._base import analytics_task, has_col, to_month_str


@analytics_task("A08_aov_trends", "aov")
def run_aov_trends(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at", amount_col])

    overall_aov = float(df[amount_col].mean())

    # Monthly AOV
    df["_month"] = df["created_at"].dt.to_period("M")
    monthly = df.groupby("_month").agg(
        aov=(amount_col, "mean"),
        orders=(amount_col, "count"),
    ).reset_index()
    monthly["period"] = monthly["_month"].apply(to_month_str)
    trend = monthly[["period", "aov", "orders"]].to_dict("records")

    # By region
    by_region = []
    if has_col(df, "region"):
        rg = df.groupby("region")[amount_col].mean().reset_index()
        rg.columns = ["region", "aov"]
        by_region = rg.sort_values("aov", ascending=False).to_dict("records")

    # Histogram (20 bins)
    amounts = df[amount_col].dropna().values
    if len(amounts) > 0:
        counts, edges = np.histogram(amounts, bins=20)
        histogram = [
            {"bin_label": f"{edges[i]:.0f}-{edges[i+1]:.0f}", "count": int(counts[i])}
            for i in range(len(counts))
        ]
    else:
        histogram = []

    return {
        "overall_aov": round(overall_aov, 2),
        "trend": trend,
        "by_region": by_region,
        "histogram": histogram,
    }
