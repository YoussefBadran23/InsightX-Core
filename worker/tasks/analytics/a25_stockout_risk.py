"""A25 — Stock-Out Risk.

For each product, computes recent sales velocity (units/day over the last 30
days) and projects days-to-stockout from `stock_qty`. Flags products by risk
tier: critical (≤7d), warning (8-30d), healthy (>30d), zero-velocity (no
recent sales).

Required columns:  product_id, quantity, stock_qty
Optional:          order_date, reorder_level, product_name, category
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


RECENT_DAYS = 30
CRITICAL_DAYS = 7
WARNING_DAYS = 30


@register(
    key="A25_stockout_risk",
    analysis_type="product",
    required_cols=["product_id", "quantity", "stock_qty"],
    optional_cols=["order_date", "reorder_level", "product_name", "category"],
    description="Days-to-stockout projection per SKU from recent sales velocity.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["quantity"] = coerce_numeric(df["quantity"]).fillna(0)
    df["stock_qty"] = coerce_numeric(df["stock_qty"]).fillna(0)
    df = df.dropna(subset=["product_id"])
    df["product_id"] = df["product_id"].astype(str)
    df = df[df["quantity"] >= 0]

    if df.empty:
        return _empty("no rows with product_id + quantity + stock_qty")

    has_date = has_col(df, "order_date")
    if has_date:
        df["order_date"] = coerce_date(df["order_date"])

    # Velocity window: prefer recent N days if dates available, else use all data.
    if has_date and df["order_date"].notna().any():
        cutoff = df["order_date"].max() - pd.Timedelta(days=RECENT_DAYS)
        recent = df[df["order_date"] >= cutoff]
        window_days = RECENT_DAYS
    else:
        recent = df
        window_days = 1  # fallback so units/day = total units

    velocity = recent.groupby("product_id")["quantity"].sum() / window_days

    # Stock + reorder level: pick the latest values per product.
    latest = df.drop_duplicates("product_id", keep="last").set_index("product_id")
    stock = latest["stock_qty"]
    reorder = latest.get("reorder_level")
    if reorder is not None:
        reorder = coerce_numeric(reorder).fillna(0)

    name_map = {}
    cat_map = {}
    if has_col(df, "product_name"):
        name_map = (
            df.dropna(subset=["product_name"])
              .drop_duplicates("product_id")
              .set_index("product_id")["product_name"].astype(str).to_dict()
        )
    if has_col(df, "category"):
        cat_map = (
            df.dropna(subset=["category"])
              .drop_duplicates("product_id")
              .set_index("product_id")["category"].astype(str).to_dict()
        )

    products: list[dict[str, Any]] = []
    for pid in latest.index:
        v = float(velocity.get(pid, 0))
        s = float(stock.loc[pid])
        if v <= 0:
            days = None
            tier = "no_velocity"
        elif s <= 0:
            days = 0
            tier = "out_of_stock"
        else:
            days = s / v
            if days <= CRITICAL_DAYS:
                tier = "critical"
            elif days <= WARNING_DAYS:
                tier = "warning"
            else:
                tier = "healthy"

        rec: dict[str, Any] = {
            "product_id":      str(pid),
            "name":            name_map.get(str(pid)),
            "category":        cat_map.get(str(pid)),
            "stock_qty":       int(s),
            "velocity_per_day": round(v, 3),
            "days_to_stockout": round(days, 2) if days is not None else None,
            "tier":            tier,
        }
        if reorder is not None:
            rec["reorder_level"] = int(reorder.get(pid, 0))
            rec["below_reorder"] = bool(s <= reorder.get(pid, 0))
        products.append(rec)

    products.sort(key=lambda r: (r["days_to_stockout"] if r["days_to_stockout"] is not None else 9999))

    tier_counts: dict[str, int] = {}
    for p in products:
        tier_counts[p["tier"]] = tier_counts.get(p["tier"], 0) + 1

    return {
        "summary": {
            "n_products":     len(products),
            "velocity_window_days": window_days,
            "critical_count": tier_counts.get("critical", 0),
            "warning_count":  tier_counts.get("warning", 0),
            "healthy_count":  tier_counts.get("healthy", 0),
            "no_velocity_count": tier_counts.get("no_velocity", 0),
            "out_of_stock_count": tier_counts.get("out_of_stock", 0),
        },
        "by_tier":    [{"tier": t, "count": c} for t, c in tier_counts.items()],
        "critical_products": [p for p in products if p["tier"] in ("critical", "out_of_stock")][:25],
        "all_products": products[:100],  # cap payload
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_products": 0, "velocity_window_days": RECENT_DAYS,
            "critical_count": 0, "warning_count": 0, "healthy_count": 0,
            "no_velocity_count": 0, "out_of_stock_count": 0,
        },
        "by_tier": [], "critical_products": [], "all_products": [],
        "warning": warning,
    }
