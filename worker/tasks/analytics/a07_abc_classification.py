"""A07 — ABC Pareto Classification.

Classic Pareto / ABC inventory tiering. Products are ranked by revenue
descending, then bucketed by cumulative-revenue threshold:

    Tier A:   top  80% of revenue   (typically ~20% of SKUs — your hero products)
    Tier B:   next 15% of revenue   (~30% of SKUs — solid B-list)
    Tier C:   bottom 5%            (~50% of SKUs — long tail / candidates for delisting)

The module also reports a Pareto check: what % of revenue actually comes from
the top 20% of products. ~80% means the dataset cleanly follows the 80/20
rule. Significant deviations are flagged.

Required columns:  product_id, total_amount
Optional columns:  net_amount, product_name, category, brand, quantity, cost_amount

Output schema::

    {
      "summary": {
        "total_revenue":  float,
        "n_products":     int,
        "tier_a":         {"products": int, "products_pct": float,
                           "revenue": float, "revenue_pct": float},
        "tier_b":         {...},
        "tier_c":         {...},
        "pareto_check":   {"top_20pct_revenue_share": float,
                           "follows_pareto":          bool}
      },
      "by_tier":   [{"tier": "A"|"B"|"C", "products": int, "revenue": float,
                     "revenue_pct": float, "products_pct": float,
                     "avg_revenue_per_product": float}],
      "products":  [{"product_id": str, "name": str|null, "category": str|null,
                     "revenue": float, "orders": int, "quantity": int,
                     "rank": int, "cumulative_pct": float, "tier": str}],
      "pareto_curve": [{"product_pct": float, "revenue_pct": float}],
      "by_category":  [{"category": str, "tier_a": int, "tier_b": int,
                        "tier_c": int, "total_products": int}],
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_numeric, has_col, register


# Standard ABC cutoffs. Some texts use 70/20/10; the 80/15/5 split is the most
# common in supply-chain practice (matches the classic Pareto principle).
TIER_A_CUTOFF = 80.0  # cumulative revenue %
TIER_B_CUTOFF = 95.0
TOP_PRODUCTS_LIMIT = 50
PARETO_CURVE_POINTS = 100


def _tier_for(cumulative_pct: float) -> str:
    if cumulative_pct <= TIER_A_CUTOFF:
        return "A"
    if cumulative_pct <= TIER_B_CUTOFF:
        return "B"
    return "C"


@register(
    key="A07_abc_classification",
    analysis_type="product",
    required_cols=["product_id", "total_amount"],
    optional_cols=["net_amount", "product_name", "category", "brand",
                   "quantity", "cost_amount"],
    description="Pareto / ABC classification of products by revenue contribution.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    if has_col(df, "quantity"):
        df["quantity"] = coerce_numeric(df["quantity"])

    revenue_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["product_id", revenue_col])
    df = df[df[revenue_col] >= 0]
    df["product_id"] = df["product_id"].astype(str)
    df["_revenue"] = df[revenue_col]

    if df.empty or df["product_id"].nunique() == 0:
        return {
            "summary": {
                "total_revenue": 0.0, "n_products": 0,
                "tier_a": {"products": 0, "products_pct": 0.0, "revenue": 0.0, "revenue_pct": 0.0},
                "tier_b": {"products": 0, "products_pct": 0.0, "revenue": 0.0, "revenue_pct": 0.0},
                "tier_c": {"products": 0, "products_pct": 0.0, "revenue": 0.0, "revenue_pct": 0.0},
                "pareto_check": {"top_20pct_revenue_share": 0.0, "follows_pareto": False},
            },
            "by_tier": [], "products": [], "pareto_curve": [], "by_category": [],
            "warning": "no rows with both product_id and revenue after coercion",
        }

    # ── Per-product aggregation ─────────────────────────────────────────────
    name_map: dict[str, str] = {}
    if has_col(df, "product_name"):
        name_map = (
            df.dropna(subset=["product_name"])
              .drop_duplicates(subset="product_id")
              .set_index("product_id")["product_name"].astype(str).to_dict()
        )
    cat_map: dict[str, str] = {}
    if has_col(df, "category"):
        cat_map = (
            df.dropna(subset=["category"])
              .drop_duplicates(subset="product_id")
              .set_index("product_id")["category"].astype(str).to_dict()
        )

    agg_dict = {"revenue": ("_revenue", "sum"), "orders": ("_revenue", "count")}
    if has_col(df, "quantity"):
        agg_dict["quantity"] = ("quantity", "sum")
    prod = df.groupby("product_id").agg(**agg_dict).reset_index()
    if "quantity" not in prod.columns:
        prod["quantity"] = 0

    prod = prod.sort_values("revenue", ascending=False).reset_index(drop=True)
    total_rev = float(prod["revenue"].sum())
    prod["rank"] = prod.index + 1
    prod["cumulative_revenue"] = prod["revenue"].cumsum()
    prod["cumulative_pct"] = (prod["cumulative_revenue"] / total_rev * 100).round(4) \
        if total_rev > 0 else 0.0
    prod["tier"] = prod["cumulative_pct"].apply(_tier_for)

    n_products = int(len(prod))

    # ── Tier summaries ──────────────────────────────────────────────────────
    by_tier_records = []
    tier_summaries: dict[str, dict[str, Any]] = {}
    for tier in ("A", "B", "C"):
        sub = prod[prod["tier"] == tier]
        n = int(len(sub))
        rev = float(sub["revenue"].sum())
        rec = {
            "tier": tier,
            "products": n,
            "products_pct": round(n / n_products * 100, 2) if n_products else 0.0,
            "revenue": round(rev, 2),
            "revenue_pct": round(rev / total_rev * 100, 2) if total_rev else 0.0,
            "avg_revenue_per_product": round(rev / n, 2) if n else 0.0,
        }
        by_tier_records.append(rec)
        tier_summaries[tier] = {
            "products": rec["products"],
            "products_pct": rec["products_pct"],
            "revenue": rec["revenue"],
            "revenue_pct": rec["revenue_pct"],
        }

    # ── Pareto check (what % of revenue from top 20% of products) ───────────
    n_top20 = max(1, int(round(n_products * 0.20)))
    top20_rev = float(prod.head(n_top20)["revenue"].sum())
    top20_share = round(top20_rev / total_rev * 100, 2) if total_rev else 0.0
    follows = 70.0 <= top20_share <= 90.0

    # ── Top products + tier-transition rows ─────────────────────────────────
    # Capture the top 50, plus a few rows around each tier boundary so the
    # transitions are visible in the output.
    top_n = prod.head(TOP_PRODUCTS_LIMIT).copy()
    transitions = []
    for tier in ("A", "B"):
        last_idx = prod[prod["tier"] == tier].index.max()
        if pd.notna(last_idx):
            li = int(last_idx)
            window = prod.iloc[max(0, li): min(n_products, li + 2)]
            transitions.append(window)
    if transitions:
        extra = pd.concat(transitions)
        top_n = pd.concat([top_n, extra]).drop_duplicates(subset="product_id").sort_values("rank")

    products_out = [
        {
            "product_id": str(r["product_id"]),
            "name": name_map.get(str(r["product_id"])),
            "category": cat_map.get(str(r["product_id"])),
            "revenue": round(float(r["revenue"]), 2),
            "orders": int(r["orders"]),
            "quantity": int(r["quantity"]) if pd.notna(r["quantity"]) else 0,
            "rank": int(r["rank"]),
            "cumulative_pct": float(r["cumulative_pct"]),
            "tier": str(r["tier"]),
        }
        for r in top_n.to_dict("records")
    ]

    # ── Pareto curve (Lorenz-style cumulative) ──────────────────────────────
    # Sample at evenly spaced product percentiles for charting.
    pareto_curve = []
    if n_products > 0:
        sample_idx = np.linspace(0, n_products - 1, min(PARETO_CURVE_POINTS, n_products), dtype=int)
        for i in sample_idx:
            pareto_curve.append({
                "product_pct": round((i + 1) / n_products * 100, 2),
                "revenue_pct": float(prod.iloc[i]["cumulative_pct"]),
            })

    # ── ABC mix per category ────────────────────────────────────────────────
    by_category: list[dict[str, Any]] = []
    if cat_map:
        prod["_category"] = prod["product_id"].map(cat_map)
        cat_pivot = (
            prod.dropna(subset=["_category"])
                .groupby("_category")["tier"]
                .value_counts().unstack(fill_value=0)
                .reindex(columns=["A", "B", "C"], fill_value=0)
                .reset_index().rename(columns={"_category": "category"})
        )
        cat_pivot["total_products"] = cat_pivot[["A", "B", "C"]].sum(axis=1)
        cat_pivot = cat_pivot.sort_values("total_products", ascending=False)
        for r in cat_pivot.to_dict("records"):
            by_category.append({
                "category": str(r["category"]),
                "tier_a": int(r["A"]),
                "tier_b": int(r["B"]),
                "tier_c": int(r["C"]),
                "total_products": int(r["total_products"]),
            })

    return {
        "summary": {
            "total_revenue": round(total_rev, 2),
            "n_products": n_products,
            "tier_a": tier_summaries["A"],
            "tier_b": tier_summaries["B"],
            "tier_c": tier_summaries["C"],
            "pareto_check": {
                "top_20pct_revenue_share": top20_share,
                "follows_pareto": bool(follows),
            },
        },
        "by_tier": by_tier_records,
        "products": products_out,
        "pareto_curve": pareto_curve,
        "by_category": by_category,
        "warning": None,
    }
