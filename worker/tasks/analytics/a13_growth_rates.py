"""A13 — Period-over-Period Growth Rates (Optimized)."""
import pandas as pd
from ._base import analytics_task, has_col, to_month_str

# RAM Optimization
COLS = ["total_amount", "net_amount", "created_at", "region"]

@analytics_task("A13_growth_rates", "growth", required_cols=COLS)
def run_growth_rates(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["created_at", amount_col])

    # Helper for Period Growth
    def get_growth(df, freq):
        agg = df.groupby(df["created_at"].dt.to_period(freq))[amount_col].sum().reset_index()
        agg.columns = ["period", "revenue"]
        agg["growth_pct"] = agg["revenue"].pct_change().mul(100).round(2)
        agg["period"] = agg["period"].astype(str)
        return agg.to_dict("records")

    # 1. Global Growth Rates
    monthly_data = get_growth(df, "M")
    quarterly_data = get_growth(df, "Q")
    
    # 2. Regional Growth (Performance Win: No Loops)
    by_region = []
    if has_col(df, "region"):
        reg_agg = df.groupby(["region", df["created_at"].dt.to_period("M")])[amount_col].sum().reset_index()
        reg_agg["growth"] = reg_agg.groupby("region")[amount_col].pct_change().mul(100)
        
        region_summary = reg_agg.groupby("region").agg(
            avg_monthly_growth_pct=("growth", "mean"),
            total_revenue=(amount_col, "sum")
        ).reset_index()
        by_region = region_summary.round(2).to_dict("records")

    # 3. CAGR Calculation
    yearly = df.groupby(df["created_at"].dt.year)[amount_col].sum()
    cagr = None
    if len(yearly) >= 2 and yearly.iloc[0] > 0:
        cagr = round(((yearly.iloc[-1] / yearly.iloc[0]) ** (1 / (len(yearly)-1)) - 1) * 100, 2)

    return {
        "monthly": monthly_data,
        "quarterly": quarterly_data,
        "cagr": cagr,
        "by_region": by_region
    }