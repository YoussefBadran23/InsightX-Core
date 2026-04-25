"""A11 — Order Status Distribution.

Count, percentage, and revenue per status. Monthly trends. By region.
"""

import pandas as pd
from ._base import analytics_task, has_col, to_month_str


@analytics_task("A11_order_status", "order_status")
def run_order_status(df, session, job_id):
    df = df.dropna(subset=["status"])
    total = len(df)

    amount_col = "total_amount" if has_col(df, "total_amount") else None

    # Distribution
    dist = df["status"].value_counts().reset_index()
    dist.columns = ["status", "count"]
    dist["pct"] = (dist["count"] / total * 100).round(2)
    if amount_col:
        rev_by_status = df.groupby("status")[amount_col].sum()
        dist["revenue"] = dist["status"].map(rev_by_status).fillna(0)
    else:
        dist["revenue"] = 0
    distribution = dist.to_dict("records")

    # Monthly trend
    trend = []
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df["_month"] = df["created_at"].dt.to_period("M")
        pivot = df.groupby(["_month", "status"]).size().unstack(fill_value=0).reset_index()
        pivot["period"] = pivot["_month"].apply(to_month_str)
        status_cols = [c for c in pivot.columns if c not in ("_month", "period")]
        trend = []
        for _, row in pivot.iterrows():
            entry = {"period": row["period"]}
            for sc in status_cols:
                entry[sc] = int(row[sc])
            trend.append(entry)

    # By region
    by_region = []
    if has_col(df, "region"):
        rg = df.groupby(["region", "status"]).size().unstack(fill_value=0).reset_index()
        for _, row in rg.iterrows():
            entry = {"region": row["region"]}
            for sc in [c for c in rg.columns if c != "region"]:
                entry[sc] = int(row[sc])
            by_region.append(entry)

    return {
        "distribution": distribution,
        "trend": trend,
        "by_region": by_region,
    }
