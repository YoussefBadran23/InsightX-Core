"""P05 — Stock Health.

Traffic-light view of every SKU: healthy / low / out-of-stock / overstock.
Distinct from A25 (which forecasts days-to-stockout based on velocity); this
is a snapshot inventory-state report.

Required columns:  product_id, stock_qty
Optional:          reorder_level, product_name, total_amount, category
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_numeric, has_col, register


DEFAULT_LOW_THRESHOLD = 10
OVERSTOCK_FACTOR = 5  # > 5× reorder_level (or 5× median) → overstocked


@register(
    key="P05_stock_health",
    analysis_type="product",
    required_cols=["product_id", "stock_qty"],
    optional_cols=["reorder_level", "product_name", "total_amount", "category"],
    description="Snapshot stock-state classification per SKU.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["stock_qty"] = coerce_numeric(df["stock_qty"]).fillna(0)
    df = df.dropna(subset=["product_id"])
    df["product_id"] = df["product_id"].astype(str)

    if df.empty:
        return _empty("no rows with product_id + stock_qty")

    # Latest stock per product
    latest = df.drop_duplicates("product_id", keep="last").set_index("product_id")

    has_reorder = "reorder_level" in latest.columns
    if has_reorder:
        latest["reorder_level"] = coerce_numeric(latest["reorder_level"]).fillna(DEFAULT_LOW_THRESHOLD)
    else:
        latest["reorder_level"] = DEFAULT_LOW_THRESHOLD

    has_rev = has_col(df, "total_amount")
    if has_rev:
        df["total_amount"] = coerce_numeric(df["total_amount"]).fillna(0)
        rev_per_product = df.groupby("product_id")["total_amount"].sum()
    else:
        rev_per_product = None

    median_stock = float(latest["stock_qty"].median()) or 1.0
    overstock_threshold = max(median_stock * OVERSTOCK_FACTOR,
                              latest["reorder_level"].median() * OVERSTOCK_FACTOR if has_reorder else median_stock * OVERSTOCK_FACTOR)

    def _classify(stock: float, reorder: float) -> str:
        if stock <= 0:
            return "out_of_stock"
        if stock <= reorder:
            return "low"
        if stock > overstock_threshold:
            return "overstock"
        return "healthy"

    latest["status"] = latest.apply(
        lambda r: _classify(float(r["stock_qty"]), float(r["reorder_level"])),
        axis=1,
    )

    name_map = {}
    cat_map = {}
    if has_col(df, "product_name"):
        name_map = df.dropna(subset=["product_name"]).drop_duplicates("product_id").set_index("product_id")["product_name"].astype(str).to_dict()
    if has_col(df, "category"):
        cat_map = df.dropna(subset=["category"]).drop_duplicates("product_id").set_index("product_id")["category"].astype(str).to_dict()

    products = []
    for pid, r in latest.iterrows():
        rec: dict[str, Any] = {
            "product_id":      str(pid),
            "name":            name_map.get(str(pid)),
            "category":        cat_map.get(str(pid)),
            "stock_qty":       int(r["stock_qty"]),
            "reorder_level":   int(r["reorder_level"]) if has_reorder else None,
            "status":          r["status"],
        }
        if rev_per_product is not None:
            rec["total_revenue"] = round(float(rev_per_product.get(str(pid), 0)), 2)
        products.append(rec)

    # Status counts
    status_counts: dict[str, int] = {}
    for p in products:
        status_counts[p["status"]] = status_counts.get(p["status"], 0) + 1

    products.sort(key=lambda r: r["stock_qty"])

    return {
        "summary": {
            "n_products":          len(products),
            "median_stock":        round(median_stock, 2),
            "overstock_threshold": round(overstock_threshold, 2),
            "out_of_stock_count":  status_counts.get("out_of_stock", 0),
            "low_count":           status_counts.get("low", 0),
            "healthy_count":       status_counts.get("healthy", 0),
            "overstock_count":     status_counts.get("overstock", 0),
        },
        "by_status":   [{"status": s, "count": c} for s, c in status_counts.items()],
        "critical":    [p for p in products if p["status"] in ("out_of_stock", "low")][:50],
        "overstocked": [p for p in products if p["status"] == "overstock"][:25],
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_products": 0, "median_stock": 0.0, "overstock_threshold": 0.0,
            "out_of_stock_count": 0, "low_count": 0,
            "healthy_count": 0, "overstock_count": 0,
        },
        "by_status": [], "critical": [], "overstocked": [],
        "warning": warning,
    }
