"""A01 — Revenue Summary (Optimized)."""
import pandas as pd
from ._base import analytics_task, has_col, to_month_str

# RAM Optimization: Only load revenue and categorical columns
COLS = ["total_amount", "net_amount", "created_at", "region", "currency"]

@analytics_task("A01_revenue_summary", "revenue", required_cols=COLS)
def run_revenue_summary(df, session, job_id):
    # Determine the primary revenue column
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    
    # Ensure strict datetime conversion
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at", amount_col])

    total = float(df[amount_col].sum())
    order_count = len(df)
    
    # Calculate daily averages safely
    date_min, date_max = df["created_at"].min(), df["created_at"].max()
    n_days = max((date_max - date_min).days, 1)

    # 1. Daily Aggregation
    daily = df.groupby(df["created_at"].dt.date)[amount_col].sum().reset_index()
    daily.columns = ["date", "revenue"]
    daily = daily.sort_values("date")

    # 2. Monthly Aggregation
    df["_month"] = df["created_at"].dt.to_period("M")
    monthly = df.groupby("_month")[amount_col].sum().reset_index()
    monthly.columns = ["period", "revenue"]
    monthly["period"] = monthly["period"].apply(to_month_str)

    # 3. Categorical Breakdowns (Region & Currency)
    breakdowns = {}
    for col in ["region", "currency"]:
        if has_col(df, col):
            bg = df.groupby(col)[amount_col].sum().reset_index()
            bg.columns = [col, "revenue"]
            bg["pct"] = (bg["revenue"] / total * 100).round(2)
            breakdowns[col] = bg.sort_values("revenue", ascending=False).to_dict("records")

    return {
        "summary": {
            "total": total,
            "avg_daily": round(total / n_days, 2),
            "order_count": order_count,
            "date_range": {"start": str(date_min.date()), "end": str(date_max.date())},
        },
        "by_period": {
            "daily": [{"date": str(r["date"]), "revenue": r["revenue"]} for r in daily.to_dict("records")],
            "monthly": monthly.to_dict("records"),
        },
        "by_region": breakdowns.get("region", []),
        "by_currency": breakdowns.get("currency", []),
        "top_days": daily.nlargest(10, "revenue").assign(date=lambda x: x['date'].astype(str)).to_dict("records")
    }