"""P04 — Per-Product Sales Trend.

Weekly time-series for each of the top-N products by revenue. Used for
small-multiples charts on the product detail page.

Required columns:  product_id, total_amount, order_date
Optional:          product_name, net_amount, quantity
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


TOP_N_PRODUCTS = 15
MAX_WEEKS = 52


@register(
    key="P04_product_sales_trend",
    analysis_type="product",
    required_cols=["product_id", "total_amount", "order_date"],
    optional_cols=["product_name", "net_amount", "quantity"],
    description="Weekly revenue + units for top-N products.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["product_id", "order_date", amount_col])
    df = df[df[amount_col] >= 0]
    df["product_id"] = df["product_id"].astype(str)

    if df.empty:
        return _empty("no rows after coercion")

    has_qty = has_col(df, "quantity")
    if has_qty:
        df["quantity"] = coerce_numeric(df["quantity"]).fillna(0)

    name_map = {}
    if has_col(df, "product_name"):
        name_map = df.dropna(subset=["product_name"]).drop_duplicates("product_id").set_index("product_id")["product_name"].astype(str).to_dict()

    # Pick the top-N products by revenue
    top_products = (
        df.groupby("product_id")[amount_col].sum()
          .sort_values(ascending=False).head(TOP_N_PRODUCTS).index.tolist()
    )

    df["_week"] = df["order_date"].dt.to_period("W").astype(str)

    series = []
    for pid in top_products:
        sub = df[df["product_id"] == pid]
        agg_kwargs = {"revenue": (amount_col, "sum"), "orders": (amount_col, "count")}
        if has_qty:
            agg_kwargs["units"] = ("quantity", "sum")
        weekly = sub.groupby("_week").agg(**agg_kwargs).reset_index().sort_values("_week")
        weekly = weekly.tail(MAX_WEEKS)
        points = []
        for r in weekly.to_dict("records"):
            pt = {
                "week":    r["_week"],
                "revenue": round(float(r["revenue"]), 2),
                "orders":  int(r["orders"]),
            }
            if has_qty:
                pt["units"] = int(r["units"])
            points.append(pt)
        series.append({
            "product_id":    pid,
            "name":          name_map.get(pid),
            "total_revenue": round(float(sub[amount_col].sum()), 2),
            "n_weeks":       int(len(points)),
            "weekly":        points,
        })

    return {
        "summary": {
            "n_products_charted": len(series),
            "total_products":     int(df["product_id"].nunique()),
            "weeks_max":          MAX_WEEKS,
        },
        "series": series,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {"n_products_charted": 0, "total_products": 0, "weeks_max": MAX_WEEKS},
        "series": [],
        "warning": warning,
    }
