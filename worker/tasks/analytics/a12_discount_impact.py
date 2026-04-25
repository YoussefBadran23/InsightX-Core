"""A12 — Discount Impact Analysis.

Discounted vs non-discounted orders, discount bands, AOV comparison, trend.
"""

import pandas as pd
from ._base import analytics_task, has_col, to_month_str


@analytics_task("A12_discount_impact", "discount_impact")
def run_discount_impact(df, session, job_id):
    df = df.dropna(subset=["total_amount", "discount_amount"])

    total_orders = len(df)
    df["has_discount"] = df["discount_amount"] > 0
    discounted = df[df["has_discount"]]
    non_discounted = df[~df["has_discount"]]

    disc_count = len(discounted)
    disc_pct = round(disc_count / total_orders * 100, 2) if total_orders else 0

    # Average discount percentage
    discounted = discounted.copy()
    discounted["discount_pct"] = (
        discounted["discount_amount"] / discounted["total_amount"] * 100
    ).clip(0, 100)
    avg_discount_pct = float(discounted["discount_pct"].mean()) if disc_count else 0

    revenue_with = float(discounted["total_amount"].sum()) if disc_count else 0
    revenue_without = float(non_discounted["total_amount"].sum())

    aov_with = float(discounted["total_amount"].mean()) if disc_count else 0
    aov_without = float(non_discounted["total_amount"].mean()) if len(non_discounted) else 0

    summary = {
        "total_orders": total_orders,
        "discounted_orders": disc_count,
        "pct_discounted": disc_pct,
        "avg_discount_pct": round(avg_discount_pct, 2),
        "revenue_with_discount": revenue_with,
        "revenue_without_discount": revenue_without,
        "aov_with_discount": round(aov_with, 2),
        "aov_without_discount": round(aov_without, 2),
    }

    # Discount bands
    if disc_count > 0:
        bins = [0, 5, 10, 15, 20, 30, 50, 100]
        labels = ["0-5%", "5-10%", "10-15%", "15-20%", "20-30%", "30-50%", "50%+"]
        discounted["band"] = pd.cut(discounted["discount_pct"], bins=bins, labels=labels, right=True)
        band_stats = discounted.groupby("band", observed=True).agg(
            count=("total_amount", "count"),
            avg_order=("total_amount", "mean"),
        ).reset_index()
        band_stats["band"] = band_stats["band"].astype(str)
        by_band = band_stats.to_dict("records")
    else:
        by_band = []

    # Monthly trend
    trend = []
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df["_month"] = df["created_at"].dt.to_period("M")
        monthly = df.groupby("_month").agg(
            total_orders=("total_amount", "count"),
            discounted_orders=("has_discount", "sum"),
            total_discount=("discount_amount", "sum"),
        ).reset_index()
        monthly["period"] = monthly["_month"].apply(to_month_str)
        monthly["discount_rate"] = (monthly["discounted_orders"] / monthly["total_orders"] * 100).round(2)
        trend = monthly[["period", "total_orders", "discounted_orders", "total_discount", "discount_rate"]].to_dict("records")

    return {
        "summary": summary,
        "by_band": by_band,
        "trend": trend,
    }
