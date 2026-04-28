"""A11 — Order Status Distribution (Optimized)."""
import pandas as pd
from ._base import analytics_task, has_col, to_month_str

# RAM Optimization: Only load status and context columns
COLS = ["status", "total_amount", "created_at", "region"]

@analytics_task("A11_order_status", "order_status", required_cols=COLS)
def run_order_status(df, session, job_id):
    df = df.dropna(subset=["status"])
    total_orders = len(df)
    amount_col = "total_amount" if has_col(df, "total_amount") else None

    # 1. Distribution Aggregation
    agg_map = {"count": ("status", "count")}
    if amount_col:
        agg_map["revenue"] = (amount_col, "sum")
    
    dist = df.groupby("status").agg(**agg_map).reset_index()
    dist["pct"] = (dist["count"] / total_orders * 100).round(2)

    # 2. Monthly Trend (Vectorized Pivot)
    trend = []
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        pivot = df.groupby([df["created_at"].dt.to_period("M"), "status"]).size().unstack(fill_value=0)
        pivot.index = pivot.index.map(to_month_str)
        trend = pivot.reset_index().rename(columns={"created_at": "period"}).to_dict("records")

    # 3. Regional Status Breakdown
    by_region = []
    if has_col(df, "region"):
        region_pivot = df.groupby(["region", "status"]).size().unstack(fill_value=0)
        by_region = region_pivot.reset_index().to_dict("records")

    return {
        "distribution": dist.to_dict("records"),
        "trend": trend,
        "by_region": by_region,
    }