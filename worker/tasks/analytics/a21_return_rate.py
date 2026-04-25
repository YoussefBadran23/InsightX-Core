"""A21 — Return Rate Analysis.

Analyzes return rates per product, category, and overall.
"""

import pandas as pd
from ._base import analytics_task, has_col


@analytics_task("A21_return_rate", "returns")
def run_return_rate(df, session, job_id):
    if not has_col(df, "return_flag"):
        return {"summary": "No return_flag column", "overall_return_rate": 0}

    df = df.copy()
    df["return_flag"] = df["return_flag"].fillna(False).astype(bool)

    total_orders = len(df)
    total_returns = int(df["return_flag"].sum())
    overall_rate = round(total_returns / total_orders * 100, 2) if total_orders > 0 else 0

    result = {
        "overall_return_rate": overall_rate,
        "total_orders": total_orders,
        "total_returns": total_returns,
    }

    # Per-product return rate
    if has_col(df, "product_id"):
        prod = df.groupby("product_id").agg(
            orders=("return_flag", "count"),
            returns=("return_flag", "sum"),
        ).reset_index()
        prod["return_rate"] = (prod["returns"] / prod["orders"] * 100).round(2)
        prod = prod.sort_values("return_rate", ascending=False)
        result["by_product"] = prod.head(20).to_dict("records")

    # Per-category return rate
    if has_col(df, "category"):
        cat = df.groupby("category").agg(
            orders=("return_flag", "count"),
            returns=("return_flag", "sum"),
        ).reset_index()
        cat["return_rate"] = (cat["returns"] / cat["orders"] * 100).round(2)
        cat = cat.sort_values("return_rate", ascending=False)
        result["by_category"] = cat.to_dict("records")

    # Monthly trend
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df["month"] = df["created_at"].dt.to_period("M")
        monthly = df.groupby("month").agg(
            orders=("return_flag", "count"),
            returns=("return_flag", "sum"),
        ).reset_index()
        monthly["return_rate"] = (monthly["returns"] / monthly["orders"] * 100).round(2)
        monthly["month"] = monthly["month"].astype(str)
        result["monthly_trend"] = monthly.to_dict("records")

    return result
