"""A05 — Cohort Retention Analysis.

Monthly cohorts based on first purchase date.
Tracks retention rates for subsequent months.
Updates customers.cohort_month.
"""

import pandas as pd
from sqlalchemy import text
from ._base import analytics_task, to_month_str


@analytics_task("A05_cohort_retention", "cohort")
def run_cohort_retention(df, session, job_id):
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["customer_id", "created_at"])

    # First purchase month per customer
    first_purchase = df.groupby("customer_id")["created_at"].min().reset_index()
    first_purchase.columns = ["customer_id", "first_purchase"]
    first_purchase["cohort"] = first_purchase["first_purchase"].dt.to_period("M")

    # Merge back
    df = df.merge(first_purchase[["customer_id", "cohort"]], on="customer_id")
    df["order_month"] = df["created_at"].dt.to_period("M")
    df["period_offset"] = (df["order_month"] - df["cohort"]).apply(lambda x: x.n if hasattr(x, "n") else 0)

    # Cohort sizes
    cohort_sizes = first_purchase.groupby("cohort")["customer_id"].nunique()

    # Active customers per cohort per offset
    active = df.groupby(["cohort", "period_offset"])["customer_id"].nunique().reset_index()
    active.columns = ["cohort", "period_offset", "active"]

    # Build retention matrix
    cohorts = []
    max_offset = min(int(active["period_offset"].max()), 12) if len(active) > 0 else 0

    for cohort_period in sorted(cohort_sizes.index):
        size = int(cohort_sizes[cohort_period])
        cohort_data = active[active["cohort"] == cohort_period].set_index("period_offset")
        retention = []
        for offset in range(max_offset + 1):
            if offset in cohort_data.index:
                rate = round(int(cohort_data.loc[offset, "active"]) / size * 100, 1)
            else:
                rate = 0.0
            retention.append(rate)
        cohorts.append({
            "cohort": to_month_str(cohort_period),
            "size": size,
            "retention": retention,
        })

    # Average retention by month offset
    avg_retention = []
    for offset in range(max_offset + 1):
        rates = [c["retention"][offset] for c in cohorts if offset < len(c["retention"])]
        avg = round(sum(rates) / len(rates), 1) if rates else 0.0
        avg_retention.append({"month": offset, "avg_retention_pct": avg})

    # ── Update customers.cohort_month ───────────────────────────────────
    for _, row in first_purchase.iterrows():
        cohort_date = row["first_purchase"].date().replace(day=1)
        session.execute(
            text("""
                UPDATE customers
                SET cohort_month = :cm, updated_at = NOW()
                WHERE external_id = :cid AND (cohort_month IS NULL OR cohort_month != :cm)
            """),
            {"cm": cohort_date, "cid": row["customer_id"]},
        )
    session.commit()

    return {
        "cohorts": cohorts,
        "avg_retention": avg_retention,
        "total_cohorts": len(cohorts),
        "max_months_tracked": max_offset,
    }
