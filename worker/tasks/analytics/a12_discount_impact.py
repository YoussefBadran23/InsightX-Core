"""A12 — Discount Impact Analysis (Optimized)."""
import pandas as pd
import numpy as np
from ._base import analytics_task, has_col, to_month_str

# RAM Optimization
COLS = ["total_amount", "discount_amount", "created_at"]

@analytics_task("A12_discount_impact", "discount_impact", required_cols=COLS)
def run_discount_impact(df, session, job_id):
    df = df.dropna(subset=["total_amount", "discount_amount"])
    df["has_discount"] = df["discount_amount"] > 0
    
    # 1. Summary Statistics (Vectorized)
    total_count = len(df)
    discounted = df[df["has_discount"]]
    
    # Optimized Discount Calculation
    df["disc_pct"] = (df["discount_amount"] / df["total_amount"] * 100).replace([np.inf, -np.inf], 0).fillna(0).clip(0, 100)

    # 2. Discount Bands (Categorical Optimization)
    by_band = []
    if not discounted.empty:
        bins = [0, 5, 10, 15, 20, 30, 50, 100]
        labels = ["0-5%", "5-10%", "10-15%", "15-20%", "20-30%", "30-50%", "50%+"]
        df_bands = df[df["has_discount"]].copy()
        df_bands["band"] = pd.cut(df_bands["disc_pct"], bins=bins, labels=labels)
        by_band = df_bands.groupby("band", observed=True).agg(count=("total_amount", "count"), avg_order=("total_amount", "mean")).reset_index()
        by_band["band"] = by_band["band"].astype(str)
        by_band = by_band.to_dict("records")

    # 3. Time Series
    trend = []
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        monthly = df.groupby(df["created_at"].dt.to_period("M")).agg(
            total_orders=("total_amount", "count"),
            discounted_orders=("has_discount", "sum"),
            total_discount=("discount_amount", "sum")
        ).reset_index()
        monthly["period"] = monthly["created_at"].apply(to_month_str)
        monthly["discount_rate"] = (monthly["discounted_orders"] / monthly["total_orders"] * 100).round(2)
        trend = monthly.to_dict("records")

    return {
        "summary": {
            "pct_discounted": round((len(discounted) / total_count * 100), 2) if total_count else 0,
            "avg_discount_pct": round(float(df.loc[df["has_discount"], "disc_pct"].mean()), 2) if not discounted.empty else 0,
            "aov_with": round(float(discounted["total_amount"].mean()), 2) if not discounted.empty else 0,
            "aov_without": round(float(df[~df["has_discount"]]["total_amount"].mean()), 2) if total_count > len(discounted) else 0
        },
        "by_band": by_band,
        "trend": trend
    }