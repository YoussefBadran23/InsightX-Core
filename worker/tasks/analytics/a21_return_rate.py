"""A21 — Return Rate Analysis (Optimized & Complete)."""
import pandas as pd
from ._base import analytics_task, has_col

COLS = ["product_id", "status", "category", "total_amount"]

@analytics_task("A21_return_rate", "returns", required_cols=COLS)
def run_return_rate(df, session, job_id):
    df["is_return"] = df["status"].str.lower().str.contains("return|refund|cancel", na=False)
    total_orders = len(df)
    total_returns = int(df.is_return.sum())

    # Product Breakdown
    prod_stats = df.groupby("product_id").agg(
        orders=("is_return", "count"),
        returns=("is_return", "sum")
    ).reset_index()
    prod_stats["rate"] = (prod_stats["returns"] / prod_stats["orders"] * 100).round(2)
    
    # Category Breakdown
    cat_stats = df.groupby("category").agg(
        orders=("is_return", "count"),
        returns=("is_return", "sum")
    ).reset_index()
    cat_stats["rate"] = (cat_stats["returns"] / cat_stats["orders"] * 100).round(2)

    return {
        "overall_rate": round(total_returns / total_orders * 100, 2) if total_orders else 0,
        "total_returns": total_returns,
        "by_product": prod_stats.nlargest(10, "rate").to_dict("records"),
        "by_category": cat_stats.sort_values("rate", ascending=False).to_dict("records")
    }