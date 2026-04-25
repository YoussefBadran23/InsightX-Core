"""A09 — Top N Products / Categories.

Top 20 products by revenue and units, top categories, bottom 10 performers.
"""

import pandas as pd
from ._base import analytics_task, has_col


@analytics_task("A09_top_n_products", "top_products")
def run_top_n_products(df, session, job_id):
    df = df.dropna(subset=["product_id", "total_amount"])

    # Per-product aggregation
    agg_dict = {"total_amount": ["sum", "count"]}
    if has_col(df, "quantity"):
        agg_dict["quantity"] = "sum"

    prod = df.groupby("product_id").agg(**{
        "revenue": ("total_amount", "sum"),
        "orders": ("total_amount", "count"),
    }).reset_index()

    if has_col(df, "quantity"):
        units = df.groupby("product_id")["quantity"].sum().reset_index()
        units.columns = ["product_id", "units"]
        prod = prod.merge(units, on="product_id", how="left")
    else:
        prod["units"] = prod["orders"]

    if has_col(df, "unit_price"):
        avg_price = df.groupby("product_id")["unit_price"].mean().reset_index()
        avg_price.columns = ["product_id", "avg_price"]
        prod = prod.merge(avg_price, on="product_id", how="left")

    # Top 20 by revenue
    top_by_revenue = prod.nlargest(20, "revenue").to_dict("records")

    # Top 20 by units
    top_by_units = prod.nlargest(20, "units").to_dict("records")

    # Bottom 10 by revenue
    bottom_products = prod.nsmallest(10, "revenue").to_dict("records")

    # Top categories
    top_categories = []
    if has_col(df, "category"):
        cat = df.groupby("category").agg(
            revenue=("total_amount", "sum"),
            orders=("total_amount", "count"),
        ).reset_index()
        if has_col(df, "quantity"):
            cat_units = df.groupby("category")["quantity"].sum().reset_index()
            cat_units.columns = ["category", "units"]
            cat = cat.merge(cat_units, on="category", how="left")
        else:
            cat["units"] = cat["orders"]
        top_categories = cat.nlargest(20, "revenue").to_dict("records")

    return {
        "top_by_revenue": top_by_revenue,
        "top_by_units": top_by_units,
        "top_categories": top_categories,
        "bottom_products": bottom_products,
        "total_products": len(prod),
    }
