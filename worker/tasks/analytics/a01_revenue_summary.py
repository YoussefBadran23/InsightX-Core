"""A01 — Revenue Summary.

Daily/weekly/monthly revenue aggregation, revenue by region/currency,
top revenue days.
"""

import pandas as pd
from ._base import analytics_task, has_col, to_month_str


@analytics_task("A01_revenue_summary", "revenue")
def run_revenue_summary(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at", amount_col])

    total = float(df[amount_col].sum())
    order_count = len(df)
    date_min = df["created_at"].min()
    date_max = df["created_at"].max()
    n_days = max((date_max - date_min).days, 1)
    avg_daily = total / n_days

    # Daily
    daily = df.groupby(df["created_at"].dt.date)[amount_col].sum().reset_index()
    daily.columns = ["date", "revenue"]
    daily = daily.sort_values("date")

    # Monthly
    df["_month"] = df["created_at"].dt.to_period("M")
    monthly = df.groupby("_month")[amount_col].sum().reset_index()
    monthly.columns = ["period", "revenue"]
    monthly["period"] = monthly["period"].apply(to_month_str)

    # By region
    by_region = []
    if has_col(df, "region"):
        rg = df.groupby("region")[amount_col].sum().reset_index()
        rg.columns = ["region", "revenue"]
        rg["pct"] = (rg["revenue"] / total * 100).round(2)
        by_region = rg.sort_values("revenue", ascending=False).to_dict("records")

    # By currency
    by_currency = []
    if has_col(df, "currency"):
        cr = df.groupby("currency")[amount_col].sum().reset_index()
        cr.columns = ["currency", "revenue"]
        by_currency = cr.sort_values("revenue", ascending=False).to_dict("records")

    # Top 10 days
    top_days = daily.nlargest(10, "revenue").to_dict("records")
    for d in top_days:
        d["date"] = str(d["date"])

    return {
        "summary": {
            "total": total,
            "avg_daily": round(avg_daily, 2),
            "order_count": order_count,
            "date_range": {"start": str(date_min.date()), "end": str(date_max.date())},
        },
        "by_period": {
            "daily": [{"date": str(r["date"]), "revenue": r["revenue"]} for r in daily.to_dict("records")],
            "monthly": monthly.to_dict("records"),
        },
        "by_region": by_region,
        "by_currency": by_currency,
        "top_days": top_days,
    }
