"""A09 — Top N Products / Categories (Optimized)."""
import pandas as pd
from ._base import analytics_task, has_col

COLS = ["product_id", "total_amount", "quantity", "unit_price", "category"]

@analytics_task("A09_top_n_products", "top_products", required_cols=COLS)
def run_top_n_products(df, session, job_id):
    df = df.dropna(subset=["product_id", "total_amount"])

    agg_map = {"revenue": ("total_amount", "sum"), "orders": ("total_amount", "count")}
    if has_col(df, "quantity"): agg_map["units"] = ("quantity", "sum")
    if has_col(df, "unit_price"): agg_map["avg_price"] = ("unit_price", "mean")

    prod = df.groupby("product_id").agg(**agg_map).reset_index()
    if "units" not in prod: prod["units"] = prod["orders"]

    top_categories = []
    if has_col(df, "category"):
        cat_agg = {"revenue": ("total_amount", "sum"), "orders": ("total_amount", "count")}
        if has_col(df, "quantity"): cat_agg["units"] = ("quantity", "sum")
        cat = df.groupby("category").agg(**cat_agg).reset_index()
        top_categories = cat.nlargest(20, "revenue").to_dict("records")

    return {"top_by_revenue": prod.nlargest(20, "revenue").to_dict("records"), "top_by_units": prod.nlargest(20, "units").to_dict("records"), 
            "top_categories": top_categories, "bottom_products": prod.nsmallest(10, "revenue").to_dict("records"), "total_products": len(prod)}