"""A07 — ABC Tier Classification (Optimized)."""
from datetime import date
import pandas as pd
from sqlalchemy import text
from ._base import analytics_task, has_col

COLS = ["product_id", "total_amount", "quantity"]

@analytics_task("A07_abc_classification", "abc_tier", required_cols=COLS)
def run_abc_classification(df, session, job_id):
    df = df.dropna(subset=["product_id", "total_amount"])

    prod = df.groupby("product_id").agg(
        revenue=("total_amount", "sum"),
        orders=("total_amount", "count"),
        units=("quantity", "sum") if has_col(df, "quantity") else ("total_amount", "count")
    ).reset_index().sort_values("revenue", ascending=False)

    total_rev = prod["revenue"].sum()
    prod["cum_pct"] = (prod["revenue"].cumsum() / (total_rev if total_rev > 0 else 1) * 100).round(2)

    prod["tier"] = "C"
    prod.loc[prod["cum_pct"] <= 95, "tier"] = "B"
    prod.loc[prod["cum_pct"] <= 80, "tier"] = "A"

    # PERFORMANCE WIN: Batch Update
    today = date.today()
    batch = [{"tier": r.tier, "today": today, "sku": str(r.product_id)[:20]} for r in prod.itertuples()]
    if batch:
        session.execute(text("UPDATE products SET abc_tier = :tier, abc_computed_at = :today, updated_at = NOW() WHERE sku = :sku"), batch)
        session.commit()

    return {"tiers": prod.groupby("tier").agg(count=("product_id", "count"), revenue=("revenue", "sum")).reset_index().to_dict("records"), 
            "top_products": prod.head(100).to_dict("records"), "total_revenue": float(total_rev)}