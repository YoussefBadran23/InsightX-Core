"""A13 — Period-over-Period Growth Rates.

MoM, QoQ, YoY growth. CAGR. By region.
"""

import numpy as np
import pandas as pd
from ._base import analytics_task, has_col, to_month_str


@analytics_task("A13_growth_rates", "growth")
def run_growth_rates(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at", amount_col])

    # Monthly
    df["_month"] = df["created_at"].dt.to_period("M")
    monthly = df.groupby("_month")[amount_col].sum().reset_index()
    monthly.columns = ["period", "revenue"]
    monthly = monthly.sort_values("period")
    monthly["growth_pct"] = monthly["revenue"].pct_change() * 100
    monthly["period"] = monthly["period"].apply(to_month_str)
    monthly_data = monthly.to_dict("records")

    # Quarterly
    df["_quarter"] = df["created_at"].dt.to_period("Q")
    quarterly = df.groupby("_quarter")[amount_col].sum().reset_index()
    quarterly.columns = ["period", "revenue"]
    quarterly = quarterly.sort_values("period")
    quarterly["growth_pct"] = quarterly["revenue"].pct_change() * 100
    quarterly["period"] = quarterly["period"].apply(to_month_str)
    quarterly_data = quarterly.to_dict("records")

    # Yearly
    df["_year"] = df["created_at"].dt.year
    yearly = df.groupby("_year")[amount_col].sum().reset_index()
    yearly.columns = ["period", "revenue"]
    yearly = yearly.sort_values("period")
    yearly["growth_pct"] = yearly["revenue"].pct_change() * 100
    yearly["period"] = yearly["period"].astype(str)
    yearly_data = yearly.to_dict("records")

    # CAGR
    cagr = None
    if len(yearly) >= 2:
        start_val = yearly.iloc[0]["revenue"]
        end_val = yearly.iloc[-1]["revenue"]
        n_years = len(yearly) - 1
        if start_val > 0 and end_val > 0 and n_years > 0:
            cagr = round(((end_val / start_val) ** (1 / n_years) - 1) * 100, 2)

    # By region
    by_region = []
    if has_col(df, "region"):
        for region in df["region"].dropna().unique():
            rdf = df[df["region"] == region]
            rm = rdf.groupby("_month")[amount_col].sum().reset_index()
            rm.columns = ["period", "revenue"]
            rm = rm.sort_values("period")
            rm["growth_pct"] = rm["revenue"].pct_change() * 100
            avg_growth = float(rm["growth_pct"].dropna().mean()) if len(rm) > 1 else None
            by_region.append({
                "region": region,
                "avg_monthly_growth_pct": round(avg_growth, 2) if avg_growth is not None else None,
                "total_revenue": float(rdf[amount_col].sum()),
            })

    return {
        "monthly": monthly_data,
        "quarterly": quarterly_data,
        "yearly": yearly_data,
        "cagr": cagr,
        "by_region": by_region,
    }
