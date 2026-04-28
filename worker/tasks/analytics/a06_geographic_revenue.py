"""A06 — Geographic Revenue (Optimized)."""
import pandas as pd
from ._base import analytics_task, has_col, to_month_str

COLS = ["total_amount", "region", "country", "created_at"]

@analytics_task("A06_geographic_revenue", "geo", required_cols=COLS)
def run_geographic_revenue(df, session, job_id):
    df = df.dropna(subset=["total_amount", "region"])
    total_rev = float(df["total_amount"].sum())

    def aggregate_geo(df, col_name, limit=None):
        if not has_col(df, col_name): return []
        agg = df.groupby(col_name).agg(revenue=("total_amount", "sum"), orders=("total_amount", "count")).reset_index()
        agg["aov"] = (agg["revenue"] / agg["orders"]).round(2)
        agg["pct"] = (agg["revenue"] / total_rev * 100).round(2)
        res = agg.sort_values("revenue", ascending=False)
        return res.head(limit).to_dict("records") if limit else res.to_dict("records")

    trends = []
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        pivot = df.groupby([df["created_at"].dt.to_period("M"), "region"])["total_amount"].sum().reset_index()
        pivot.columns = ["month", "region", "revenue"]
        pivot["month"] = pivot["month"].apply(to_month_str)
        trends = pivot.to_dict("records")

    return {"by_region": aggregate_geo(df, "region"), "by_country": aggregate_geo(df, "country", limit=30), "trends": trends, "total_revenue": total_rev}