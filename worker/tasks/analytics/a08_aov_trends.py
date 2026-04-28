"""A08 — Average Order Value Trends (Optimized)."""
import numpy as np
import pandas as pd
from ._base import analytics_task, has_col, to_month_str

COLS = ["total_amount", "net_amount", "created_at", "region"]

@analytics_task("A08_aov_trends", "aov", required_cols=COLS)
def run_aov_trends(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at", amount_col])

    monthly = df.groupby(df["created_at"].dt.to_period("M")).agg(aov=(amount_col, "mean"), orders=(amount_col, "count")).reset_index()
    monthly["period"] = monthly["created_at"].apply(to_month_str)

    by_region = []
    if has_col(df, "region"):
        by_region = df.groupby("region")[amount_col].mean().reset_index()
        by_region.columns = ["region", "aov"]
        by_region = by_region.sort_values("aov", ascending=False).to_dict("records")

    histogram = []
    amounts = df[amount_col].values
    if len(amounts) > 0:
        counts, edges = np.histogram(amounts, bins=20)
        histogram = [{"bin_label": f"{edges[i]:.0f}-{edges[i+1]:.0f}", "count": int(counts[i])} for i in range(len(counts))]

    return {"overall_aov": round(float(df[amount_col].mean()), 2), "trend": monthly[["period", "aov", "orders"]].to_dict("records"), 
            "by_region": by_region, "histogram": histogram}