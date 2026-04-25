"""A10 — Customer Lifetime Stats.

LTV distribution, stats (mean/median/percentiles), histogram, by cohort.
"""

import numpy as np
import pandas as pd
from ._base import analytics_task, has_col, to_month_str


@analytics_task("A10_customer_lifetime", "customer_lifetime")
def run_customer_lifetime(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", amount_col])

    # Per-customer LTV
    cust = df.groupby("customer_id").agg(
        ltv=(amount_col, "sum"),
        orders=(amount_col, "count"),
    ).reset_index()

    ltv_values = cust["ltv"].values
    total_customers = len(cust)

    # Stats
    stats = {
        "mean": float(np.mean(ltv_values)),
        "median": float(np.median(ltv_values)),
        "p25": float(np.percentile(ltv_values, 25)),
        "p75": float(np.percentile(ltv_values, 75)),
        "p90": float(np.percentile(ltv_values, 90)),
        "max": float(np.max(ltv_values)),
        "total_customers": total_customers,
    }

    # Histogram (20 bins)
    counts, edges = np.histogram(ltv_values, bins=20)
    histogram = [
        {"bin_label": f"{edges[i]:.0f}-{edges[i+1]:.0f}", "count": int(counts[i])}
        for i in range(len(counts))
    ]

    # By cohort (if created_at available)
    by_cohort = []
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        first_month = df.groupby("customer_id")["created_at"].min().dt.to_period("M").reset_index()
        first_month.columns = ["customer_id", "cohort"]
        cust = cust.merge(first_month, on="customer_id", how="left")
        cohort_stats = cust.groupby("cohort").agg(
            avg_ltv=("ltv", "mean"),
            median_ltv=("ltv", "median"),
            customers=("customer_id", "count"),
        ).reset_index()
        cohort_stats["cohort"] = cohort_stats["cohort"].apply(to_month_str)
        by_cohort = cohort_stats.to_dict("records")

    return {
        "stats": stats,
        "histogram": histogram,
        "by_cohort": by_cohort,
    }
