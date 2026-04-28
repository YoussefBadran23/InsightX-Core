"""A04 — Gross Margin Analysis (Optimized)."""
import pandas as pd
from ._base import analytics_task, has_col, to_month_str

COLS = ["total_amount", "cost_amount", "net_amount", "category", "product_id", "created_at"]

@analytics_task("A04_gross_margin", "margin", required_cols=COLS)
def run_gross_margin(df, session, job_id):
    df = df.dropna(subset=["total_amount", "cost_amount"])
    rev_col = "net_amount" if has_col(df, "net_amount") else "total_amount"

    rev_sum = float(df[rev_col].sum())
    cost_sum = float(df["cost_amount"].sum())
    margin = rev_sum - cost_sum

    def get_group_stats(df, group_col):
        if not has_col(df, group_col): return []
        stats = df.groupby(group_col).agg(revenue=(rev_col, "sum"), cost=("cost_amount", "sum")).reset_index()
        stats["margin_pct"] = ((stats["revenue"] - stats["cost"]) / stats["revenue"].replace(0, 1) * 100).round(2)
        return stats.sort_values("revenue", ascending=False).head(20).to_dict("records")

    trend = []
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        monthly = df.groupby(df["created_at"].dt.to_period("M")).agg(revenue=(rev_col, "sum"), cost=("cost_amount", "sum")).reset_index()
        monthly["period"] = monthly["created_at"].apply(to_month_str)
        monthly["margin_pct"] = ((monthly["revenue"] - monthly["cost"]) / monthly["revenue"].replace(0, 1) * 100).round(2)
        trend = monthly[["period", "revenue", "cost", "margin_pct"]].to_dict("records")

    return {
        "overall": {"revenue": rev_sum, "cost": cost_sum, "margin": margin, "pct": round(margin/rev_sum*100, 2) if rev_sum else 0},
        "by_category": get_group_stats(df, "category"),
        "by_product": get_group_stats(df, "product_id"),
        "trend": trend
    }