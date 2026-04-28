"""A14 — Acquisition Channel (Optimized)."""
import pandas as pd
from ._base import analytics_task, has_col, to_month_str

# RAM Optimization
COLS = ["acquisition_channel", "customer_id", "created_at", "total_amount"]

@analytics_task("A14_acquisition_channel", "acquisition_channel", required_cols=COLS)
def run_acquisition_channel(df, session, job_id):
    df = df.dropna(subset=["acquisition_channel", "customer_id"])
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    
    # 1. Optimized First Purchase Attribution (O(N) vs Sort O(N log N))
    if "created_at" in df.columns:
        first_idx = df.groupby("customer_id")["created_at"].idxmin()
        first = df.loc[first_idx].copy()
    else:
        first = df.drop_duplicates(subset=["customer_id"], keep="first").copy()

    total_customers = len(first)

    # 2. Vectorized Channel Metrics
    ch = first.groupby("acquisition_channel").size().reset_index(name="customers")
    
    if has_col(df, "total_amount"):
        rev = df.groupby("acquisition_channel")["total_amount"].sum().reset_index(name="revenue")
        ch = ch.merge(rev, on="acquisition_channel", how="left")
        ch["avg_ltv"] = (ch["revenue"] / ch["customers"]).round(2)

    ch["pct"] = (ch["customers"] / total_customers * 100).round(2)

    # 3. Monthly New Customer Trend
    trend = []
    if "created_at" in first.columns:
        first["month"] = first["created_at"].dt.to_period("M")
        trend = first.groupby(["month", "acquisition_channel"]).size().reset_index(name="new_customers")
        trend["month"] = trend["month"].apply(to_month_str)
        trend = trend.rename(columns={"acquisition_channel": "channel"}).to_dict("records")

    return {
        "by_channel": ch.sort_values("customers", ascending=False).to_dict("records"),
        "trend": trend,
        "total_customers": total_customers,
    }