"""A04 — Gross Margin Analysis.

Overall margin %, by category, by product (top 10), monthly trend.
"""

import pandas as pd
from ._base import analytics_task, has_col, to_month_str


@analytics_task("A04_gross_margin", "margin")
def run_gross_margin(df, session, job_id):
    df = df.dropna(subset=["total_amount", "cost_amount"])

    revenue_col = "net_amount" if has_col(df, "net_amount") else "total_amount"

    total_revenue = float(df[revenue_col].sum())
    total_cost = float(df["cost_amount"].sum())
    total_margin = total_revenue - total_cost
    margin_pct = round(total_margin / total_revenue * 100, 2) if total_revenue else 0

    overall = {
        "revenue": total_revenue,
        "cost": total_cost,
        "margin": total_margin,
        "margin_pct": margin_pct,
    }

    # By category
    by_category = []
    if has_col(df, "category"):
        cat = df.groupby("category").agg(
            revenue=(revenue_col, "sum"),
            cost=("cost_amount", "sum"),
        ).reset_index()
        cat["margin"] = cat["revenue"] - cat["cost"]
        cat["margin_pct"] = (cat["margin"] / cat["revenue"] * 100).round(2)
        by_category = cat.sort_values("margin", ascending=False).to_dict("records")

    # By product (top 10)
    by_product = []
    if has_col(df, "product_id"):
        prod = df.groupby("product_id").agg(
            revenue=(revenue_col, "sum"),
            cost=("cost_amount", "sum"),
        ).reset_index()
        prod["margin"] = prod["revenue"] - prod["cost"]
        prod["margin_pct"] = (prod["margin"] / prod["revenue"] * 100).round(2)
        by_product = prod.nlargest(10, "margin").to_dict("records")

    # Monthly trend
    trend = []
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df["_month"] = df["created_at"].dt.to_period("M")
        monthly = df.groupby("_month").agg(
            revenue=(revenue_col, "sum"),
            cost=("cost_amount", "sum"),
        ).reset_index()
        monthly["margin_pct"] = (
            (monthly["revenue"] - monthly["cost"]) / monthly["revenue"] * 100
        ).round(2)
        monthly["period"] = monthly["_month"].apply(to_month_str)
        trend = monthly[["period", "revenue", "cost", "margin_pct"]].to_dict("records")

    return {
        "overall": overall,
        "by_category": by_category,
        "by_product": by_product,
        "trend": trend,
    }
