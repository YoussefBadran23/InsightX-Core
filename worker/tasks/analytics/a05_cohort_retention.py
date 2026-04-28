"""A05 — Cohort Retention Analysis (Optimized)."""
import pandas as pd
from sqlalchemy import text
from ._base import analytics_task, to_month_str

COLS = ["customer_id", "created_at"]

@analytics_task("A05_cohort_retention", "cohort", required_cols=COLS)
def run_cohort_retention(df, session, job_id):
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["customer_id", "created_at"])

    # 1. Calculate Cohorts
    first_purchase = df.groupby("customer_id")["created_at"].min().reset_index()
    first_purchase.columns = ["customer_id", "first_purchase"]
    first_purchase["cohort"] = first_purchase["first_purchase"].dt.to_period("M")

    # 2. Calculate Retention Matrix
    df = df.merge(first_purchase[["customer_id", "cohort"]], on="customer_id")
    df["order_month"] = df["created_at"].dt.to_period("M")
    df["period_offset"] = (df["order_month"] - df["cohort"]).apply(lambda x: getattr(x, 'n', 0))

    cohort_sizes = first_purchase.groupby("cohort")["customer_id"].nunique()
    active = df.groupby(["cohort", "period_offset"])["customer_id"].nunique().reset_index()
    max_offset = min(int(active["period_offset"].max()), 12) if not active.empty else 0

    cohort_list = []
    for cp in sorted(cohort_sizes.index):
        size = int(cohort_sizes[cp])
        c_active = active[active["cohort"] == cp].set_index("period_offset")
        retention = [round(int(c_active.loc[i, "active"]) / size * 100, 1) if i in c_active.index else 0.0 for i in range(max_offset + 1)]
        cohort_list.append({"cohort": to_month_str(cp), "size": size, "retention": retention})

    # PERFORMANCE WIN: Batch Update
    batch = [{"cm": r.first_purchase.date().replace(day=1), "cid": r.customer_id} for r in first_purchase.itertuples()]
    if batch:
        session.execute(text("UPDATE customers SET cohort_month = :cm, updated_at = NOW() WHERE external_id = :cid"), batch)
        session.commit()

    return {"cohorts": cohort_list, "total_cohorts": len(cohort_list), "max_months": max_offset}