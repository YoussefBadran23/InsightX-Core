"""A14 — Customer Acquisition by Channel.

Customer count and revenue per acquisition channel.
First-purchase attribution. Monthly trend of new customers per channel.
"""

import pandas as pd
from ._base import analytics_task, has_col, to_month_str


@analytics_task("A14_acquisition_channel", "acquisition_channel")
def run_acquisition_channel(df, session, job_id):
    df = df.dropna(subset=["acquisition_channel", "customer_id"])

    # First purchase per customer → determines attribution channel
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        first = df.sort_values("created_at").drop_duplicates(subset=["customer_id"], keep="first")
    else:
        first = df.drop_duplicates(subset=["customer_id"], keep="first")

    total_customers = first["customer_id"].nunique()

    # By channel
    ch = first.groupby("acquisition_channel").agg(
        customers=("customer_id", "nunique"),
    ).reset_index()

    if has_col(df, "total_amount"):
        # Total revenue per channel (all orders, not just first)
        rev = df.groupby("acquisition_channel")["total_amount"].sum().reset_index()
        rev.columns = ["acquisition_channel", "revenue"]
        ch = ch.merge(rev, on="acquisition_channel", how="left")
        ch["avg_ltv"] = (ch["revenue"] / ch["customers"]).round(2)
    else:
        ch["revenue"] = 0
        ch["avg_ltv"] = 0

    ch["pct"] = (ch["customers"] / total_customers * 100).round(2)
    by_channel = ch.sort_values("customers", ascending=False).to_dict("records")

    # Monthly trend of new customers per channel
    trend = []
    if has_col(df, "created_at"):
        first["_month"] = first["created_at"].dt.to_period("M")
        pivot = first.groupby(["_month", "acquisition_channel"])["customer_id"].nunique().reset_index()
        pivot.columns = ["month", "channel", "new_customers"]
        pivot["month"] = pivot["month"].apply(to_month_str)
        trend = pivot.to_dict("records")

    return {
        "by_channel": by_channel,
        "trend": trend,
        "total_customers": total_customers,
    }
