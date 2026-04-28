"""A10 — Customer Lifetime Stats (Optimized)."""
import numpy as np
import pandas as pd
from ._base import analytics_task, has_col, to_month_str

COLS = ["customer_id", "total_amount", "net_amount", "created_at"]

@analytics_task("A10_customer_lifetime", "customer_lifetime", required_cols=COLS)
def run_customer_lifetime(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", amount_col])

    agg_dict = {"ltv": (amount_col, "sum"), "orders": (amount_col, "count")}
    if has_col(df, "created_at"):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        agg_dict["first_purchase"] = ("created_at", "min")

    cust = df.groupby("customer_id").agg(**agg_dict).reset_index()
    ltv_vals = cust["ltv"].values

    stats = {"mean": float(np.mean(ltv_vals)), "median": float(np.median(ltv_vals)), "p90": float(np.percentile(ltv_vals, 90)), 
             "max": float(np.max(ltv_vals)), "total_customers": len(cust)}

    counts, edges = np.histogram(ltv_vals, bins=20)
    histogram = [{"bin_label": f"{edges[i]:.0f}-{edges[i+1]:.0f}", "count": int(counts[i])} for i in range(len(counts))]

    by_cohort = []
    if "first_purchase" in cust.columns:
        cust["cohort"] = cust["first_purchase"].dt.to_period("M")
        by_cohort = cust.groupby("cohort").agg(avg_ltv=("ltv", "mean"), customers=("customer_id", "count")).reset_index()
        by_cohort["cohort"] = by_cohort["cohort"].apply(to_month_str)
        by_cohort = by_cohort.to_dict("records")

    return {"stats": stats, "histogram": histogram, "by_cohort": by_cohort}