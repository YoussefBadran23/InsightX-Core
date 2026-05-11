"""A09 — Top N Products (Multi-Metric Rankings).

Ranks products by five complementary metrics so a single product list never
hides the picture:

- **Revenue**       — pure dollar contribution
- **Orders**        — popularity / SKU velocity
- **Quantity**      — units sold (if quantity column present)
- **AOV**           — premium positioning (revenue / orders)
- **Margin**        — bottom-line contribution (if cost_amount present)

Plus a bottom-by-revenue list to surface delisting candidates.

Why not just sort by revenue?
-----------------------------
A high-revenue product might be a popular cheap SKU (high orders) or a rare
premium item (high AOV) — those are different inventory bets. A09 surfaces
both shapes side-by-side. A07 (ABC tiers) tells you *how concentrated*; A09
tells you *which products* matter on each axis.

Required columns:  product_id, total_amount
Optional columns:  net_amount, product_name, category, brand, customer_id,
                   order_id, order_date, quantity, cost_amount

Output schema::

    {
      "summary": {
        "n_products":     int,
        "total_revenue":  float,
        "total_orders":   int,
        "total_quantity": int | null
      },
      "top_by_revenue":   [...],
      "top_by_orders":    [...],
      "top_by_quantity":  [...] | null,
      "top_by_aov":       [...],   # min orders threshold to dampen 1-sale spikes
      "top_by_margin":    [...] | null,
      "bottom_by_revenue":[...],
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


TOP_N = 20
MIN_ORDERS_FOR_AOV_RANK = 3   # filter 1-sale flukes from "premium" rankings


def _build_record(r: dict, name_map: dict, cat_map: dict, brand_map: dict,
                  has_quantity: bool, has_margin: bool) -> dict[str, Any]:
    pid = str(r["product_id"])
    rec = {
        "product_id": pid,
        "name": name_map.get(pid),
        "category": cat_map.get(pid),
        "brand": brand_map.get(pid),
        "revenue": round(float(r["revenue"]), 2),
        "orders": int(r["orders"]),
        "unique_customers": int(r.get("unique_customers", 0)),
        "aov": round(float(r["aov"]), 2),
    }
    if has_quantity:
        rec["quantity"] = int(r.get("quantity", 0))
        rec["avg_unit_price"] = (
            round(float(r["revenue"]) / float(r["quantity"]), 2)
            if r.get("quantity") and r["quantity"] > 0 else 0.0
        )
    if has_margin:
        rec["cost"] = round(float(r.get("cost", 0)), 2)
        rec["margin"] = round(float(r.get("margin", 0)), 2)
        rec["margin_pct"] = round(float(r.get("margin_pct", 0)), 2)
    if r.get("first_sale") is not None and pd.notna(r["first_sale"]):
        rec["first_sale"] = str(r["first_sale"])
        rec["last_sale"] = str(r["last_sale"])
        rec["days_active"] = int(r.get("days_active", 0))
    return rec


@register(
    key="A09_top_n_products",
    analysis_type="product",
    required_cols=["product_id", "total_amount"],
    optional_cols=["net_amount", "product_name", "category", "brand",
                   "customer_id", "order_id", "order_date", "quantity",
                   "cost_amount"],
    description="Top N products ranked by revenue, orders, quantity, AOV, and margin.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    if has_col(df, "quantity"):
        df["quantity"] = coerce_numeric(df["quantity"])
    if has_col(df, "cost_amount"):
        df["cost_amount"] = coerce_numeric(df["cost_amount"])
    if has_col(df, "order_date"):
        df["order_date"] = coerce_date(df["order_date"])

    revenue_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["product_id", revenue_col])
    df = df[df[revenue_col] >= 0]
    df["product_id"] = df["product_id"].astype(str)
    df["_revenue"] = df[revenue_col]

    if df.empty:
        return {
            "summary": {"n_products": 0, "total_revenue": 0.0,
                        "total_orders": 0, "total_quantity": None},
            "top_by_revenue": [], "top_by_orders": [],
            "top_by_quantity": None, "top_by_aov": [],
            "top_by_margin": None, "bottom_by_revenue": [],
            "warning": "no rows with both product_id and revenue after coercion",
        }

    has_quantity = has_col(df, "quantity")
    has_cost = has_col(df, "cost_amount")
    has_customer = has_col(df, "customer_id")
    has_order = has_col(df, "order_id")
    has_date = has_col(df, "order_date")

    # Display-name maps. Build once so each row in each ranking can fetch the
    # human-readable label without re-grouping.
    def _build_map(col: str) -> dict[str, str]:
        if not has_col(df, col):
            return {}
        return (
            df.dropna(subset=[col])
              .drop_duplicates(subset="product_id")
              .set_index("product_id")[col].astype(str).to_dict()
        )

    name_map = _build_map("product_name")
    cat_map = _build_map("category")
    brand_map = _build_map("brand")

    # ── Per-product aggregation ─────────────────────────────────────────────
    agg_kwargs = {"revenue": ("_revenue", "sum")}

    # Order count: prefer distinct order_id when available — otherwise rows.
    if has_order:
        df["order_id"] = df["order_id"].astype(str)
        agg_kwargs["orders"] = ("order_id", "nunique")
    else:
        agg_kwargs["orders"] = ("_revenue", "count")

    if has_quantity:
        agg_kwargs["quantity"] = ("quantity", "sum")
    if has_cost:
        agg_kwargs["cost"] = ("cost_amount", "sum")
    if has_customer:
        df["customer_id"] = df["customer_id"].astype(str)
        agg_kwargs["unique_customers"] = ("customer_id", "nunique")
    if has_date:
        agg_kwargs["first_sale"] = ("order_date", "min")
        agg_kwargs["last_sale"] = ("order_date", "max")

    prod = df.groupby("product_id").agg(**agg_kwargs).reset_index()

    # Derived columns — compute once on the per-product frame.
    prod["aov"] = (prod["revenue"] / prod["orders"]).round(2)
    if has_cost:
        prod["margin"] = prod["revenue"] - prod["cost"]
        prod["margin_pct"] = (prod["margin"] / prod["revenue"].replace(0, pd.NA) * 100).round(2)
    if has_date:
        prod["first_sale"] = prod["first_sale"].dt.date
        prod["last_sale"] = prod["last_sale"].dt.date
        prod["days_active"] = (
            (pd.to_datetime(prod["last_sale"]) - pd.to_datetime(prod["first_sale"]))
            .dt.days + 1
        ).fillna(1).astype(int)
    if not has_customer:
        prod["unique_customers"] = 0

    # ── Build rankings ──────────────────────────────────────────────────────
    def _rank(sorted_df: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            _build_record(r, name_map, cat_map, brand_map, has_quantity, has_cost)
            for r in sorted_df.head(TOP_N).to_dict("records")
        ]

    top_by_revenue = _rank(prod.sort_values("revenue", ascending=False))
    top_by_orders = _rank(prod.sort_values("orders", ascending=False))

    top_by_quantity = None
    if has_quantity:
        top_by_quantity = _rank(prod.sort_values("quantity", ascending=False))

    # AOV: filter low-order products so single-sale outliers don't dominate.
    aov_eligible = prod[prod["orders"] >= MIN_ORDERS_FOR_AOV_RANK]
    top_by_aov = _rank(aov_eligible.sort_values("aov", ascending=False))

    top_by_margin = None
    if has_cost:
        top_by_margin = _rank(prod.sort_values("margin", ascending=False))

    bottom_by_revenue = _rank(
        prod[prod["revenue"] > 0].sort_values("revenue", ascending=True)
    )

    total_qty = int(prod["quantity"].sum()) if has_quantity else None
    total_orders = int(prod["orders"].sum())

    return {
        "summary": {
            "n_products": int(len(prod)),
            "total_revenue": round(float(prod["revenue"].sum()), 2),
            "total_orders": total_orders,
            "total_quantity": total_qty,
        },
        "top_by_revenue": top_by_revenue,
        "top_by_orders": top_by_orders,
        "top_by_quantity": top_by_quantity,
        "top_by_aov": top_by_aov,
        "top_by_margin": top_by_margin,
        "bottom_by_revenue": bottom_by_revenue,
        "warning": None,
    }
