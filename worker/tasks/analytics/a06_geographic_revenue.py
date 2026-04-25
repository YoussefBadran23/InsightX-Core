"""A06 — Geographic Revenue.

Revenue breakdown by region and country. Monthly trends per region.
"""

import pandas as pd
from ._base import analytics_task, has_col, to_month_str


@analytics_task("A06_geographic_revenue", "geo")
def run_geographic_revenue(df, session, job_id):
    df = df.dropna(subset=["total_amount", "region"])

    total_revenue = float(df["total_amount"].sum())

    # By region
    rg = df.groupby("region").agg(
        revenue=("total_amount", "sum"),
        orders=("total_amount", "count"),
    ).reset_index()
    rg["aov"] = (rg["revenue"] / rg["orders"]).round(2)
    rg["pct"] = (rg["revenue"] / total_revenue * 100).round(2)
    by_region = rg.sort_values("revenue", ascending=False).to_dict("records")

    # By country
    by_country = []
    if has_col(df, "country"):
        co = df.groupby("country").agg(
            revenue=("total_amount", "sum"),
            orders=("total_amount", "count"),
        ).reset_index()
        co["aov"] = (co["revenue"] / co["orders"]).round(2)
        co["pct"] = (co["revenue"] / total_revenue * 100).round(2)
        by_country = co.nlargest(30, "revenue").to_dict("records")

    # Monthly trends per region
    trends = []
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df["_month"] = df["created_at"].dt.to_period("M")
        pivot = df.groupby(["_month", "region"])["total_amount"].sum().reset_index()
        pivot.columns = ["month", "region", "revenue"]
        pivot["month"] = pivot["month"].apply(to_month_str)
        trends = pivot.to_dict("records")

    return {
        "by_region": by_region,
        "by_country": by_country,
        "trends": trends,
        "total_revenue": total_revenue,
    }
