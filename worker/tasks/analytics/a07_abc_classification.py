"""A07 — ABC Tier Classification.

Pareto (80/20) product classification by cumulative revenue.
A = top 80%, B = next 15%, C = bottom 5%.
Updates products.abc_tier and products.abc_computed_at.
"""

from datetime import date

import pandas as pd
from sqlalchemy import text
from ._base import analytics_task, has_col


@analytics_task("A07_abc_classification", "abc_tier")
def run_abc_classification(df, session, job_id):
    df = df.dropna(subset=["product_id", "total_amount"])

    # Revenue per product
    prod = df.groupby("product_id").agg(
        revenue=("total_amount", "sum"),
        orders=("total_amount", "count"),
    ).reset_index()

    if has_col(df, "quantity"):
        units = df.groupby("product_id")["quantity"].sum().reset_index()
        units.columns = ["product_id", "units"]
        prod = prod.merge(units, on="product_id", how="left")
    else:
        prod["units"] = prod["orders"]

    # Sort descending by revenue
    prod = prod.sort_values("revenue", ascending=False).reset_index(drop=True)
    total_revenue = prod["revenue"].sum()
    prod["cumulative_pct"] = (prod["revenue"].cumsum() / total_revenue * 100).round(2)

    # Assign tiers
    prod["tier"] = "C"
    prod.loc[prod["cumulative_pct"] <= 95, "tier"] = "B"
    prod.loc[prod["cumulative_pct"] <= 80, "tier"] = "A"

    # Tier summary
    tier_summary = prod.groupby("tier").agg(
        count=("product_id", "count"),
        revenue=("revenue", "sum"),
    ).reset_index()
    tier_summary["pct"] = (tier_summary["revenue"] / total_revenue * 100).round(2)
    tiers = tier_summary.to_dict("records")

    # Product list (top 100)
    products = prod.head(100)[["product_id", "revenue", "units", "cumulative_pct", "tier"]].to_dict("records")

    # ── Update products table ───────────────────────────────────────────
    today = date.today()
    for _, row in prod.iterrows():
        sku = str(row["product_id"])[:20]
        session.execute(
            text("""
                UPDATE products
                SET abc_tier = :tier, abc_computed_at = :today, updated_at = NOW()
                WHERE sku = :sku
            """),
            {"tier": row["tier"], "today": today, "sku": sku},
        )
    session.commit()

    return {
        "tiers": tiers,
        "products": products,
        "total_products": len(prod),
        "total_revenue": float(total_revenue),
    }
