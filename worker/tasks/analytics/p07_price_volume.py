"""P07 — Price vs Volume Analysis.

Scatter-style aggregation: each product is a point with (avg_unit_price,
total_units, total_revenue, n_orders). Plus a price-elasticity estimate
(naive Pearson correlation between log(price) and log(quantity) across
products) — useful as a hint, not as a causal claim.

Required columns:  product_id, unit_price, quantity
Optional:          product_name, category, total_amount, order_date
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_numeric, has_col, register


@register(
    key="P07_price_volume",
    analysis_type="product",
    required_cols=["product_id", "unit_price", "quantity"],
    optional_cols=["product_name", "category", "total_amount", "order_date"],
    description="Per-product price-vs-volume scatter + naive elasticity hint.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["unit_price"] = coerce_numeric(df["unit_price"])
    df["quantity"]   = coerce_numeric(df["quantity"]).fillna(0)
    df = df.dropna(subset=["product_id", "unit_price"])
    df = df[(df["unit_price"] > 0) & (df["quantity"] >= 0)]
    df["product_id"] = df["product_id"].astype(str)

    if df.empty:
        return _empty("no rows after coercion")

    name_map = {}
    cat_map = {}
    if has_col(df, "product_name"):
        name_map = df.dropna(subset=["product_name"]).drop_duplicates("product_id").set_index("product_id")["product_name"].astype(str).to_dict()
    if has_col(df, "category"):
        cat_map = df.dropna(subset=["category"]).drop_duplicates("product_id").set_index("product_id")["category"].astype(str).to_dict()

    agg_kwargs = {
        "avg_unit_price": ("unit_price", "mean"),
        "total_units":    ("quantity",   "sum"),
        "orders":         ("unit_price", "count"),
    }
    if has_col(df, "total_amount"):
        df["total_amount"] = coerce_numeric(df["total_amount"]).fillna(0)
        agg_kwargs["total_revenue"] = ("total_amount", "sum")

    prod = df.groupby("product_id").agg(**agg_kwargs).reset_index()

    # ── Elasticity hint: corr(log(avg_price), log(total_units)) ─────────────
    valid = prod[(prod["avg_unit_price"] > 0) & (prod["total_units"] > 0)]
    elasticity = None
    if len(valid) >= 10:
        logp = np.log(valid["avg_unit_price"].astype(float))
        logq = np.log(valid["total_units"].astype(float))
        if logp.std() > 0 and logq.std() > 0:
            elasticity = float(np.corrcoef(logp, logq)[0, 1])

    # Sort by total revenue descending (or by units if revenue absent).
    if "total_revenue" in prod.columns:
        prod = prod.sort_values("total_revenue", ascending=False)
    else:
        prod = prod.sort_values("total_units", ascending=False)

    products = []
    for r in prod.head(200).to_dict("records"):
        pid = str(r["product_id"])
        rec: dict[str, Any] = {
            "product_id":     pid,
            "name":           name_map.get(pid),
            "category":       cat_map.get(pid),
            "avg_unit_price": round(float(r["avg_unit_price"]), 2),
            "total_units":    int(r["total_units"]),
            "orders":         int(r["orders"]),
        }
        if "total_revenue" in r:
            rec["total_revenue"] = round(float(r["total_revenue"]), 2)
        products.append(rec)

    return {
        "summary": {
            "n_products":           int(len(prod)),
            "elasticity_correlation": round(elasticity, 4) if elasticity is not None else None,
            "elasticity_interpretation": _interpret_elasticity(elasticity),
            "avg_unit_price":       round(float(prod["avg_unit_price"].mean()), 2),
            "median_unit_price":    round(float(prod["avg_unit_price"].median()), 2),
        },
        "products": products,
        "warning":  None,
    }


def _interpret_elasticity(r: float | None) -> str:
    if r is None:
        return "not enough variance to estimate"
    if r < -0.3:
        return "negative correlation — higher prices tend to mean lower quantity (typical demand curve)"
    if r > 0.3:
        return "positive correlation — higher prices coincide with higher quantity (likely a confounder, e.g. premium category)"
    return "weak / no relationship between price and quantity across products"


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_products": 0, "elasticity_correlation": None,
            "elasticity_interpretation": "no data",
            "avg_unit_price": 0.0, "median_unit_price": 0.0,
        },
        "products": [],
        "warning": warning,
    }
