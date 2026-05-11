"""A24 — Market-Basket Recommendations.

Per-product "customers also bought" recommendation lists, derived from
co-occurrence in the same order_id. Builds on A03 but reorganizes the output
around the recommendation use-case: for each top product, return the N other
products most frequently bought alongside it.

Required columns:  order_id, product_id, quantity
Optional:          product_name, total_amount
"""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from typing import Any

import pandas as pd

from ._base import has_col, register


MAX_BASKET_FOR_PAIRS = 30
TOP_PRODUCTS = 30
RECOS_PER_PRODUCT = 5
MIN_PAIR_COUNT = 2


@register(
    key="A24_basket_recommendations",
    analysis_type="product",
    required_cols=["order_id", "product_id", "quantity"],
    optional_cols=["product_name", "total_amount"],
    description="Per-product recommendation list from market-basket co-occurrence.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["order_id", "product_id"])
    df["order_id"] = df["order_id"].astype(str)
    df["product_id"] = df["product_id"].astype(str)

    if df.empty:
        return _empty("no rows with order_id + product_id")

    name_map = {}
    if has_col(df, "product_name"):
        name_map = (
            df.dropna(subset=["product_name"])
              .drop_duplicates("product_id")
              .set_index("product_id")["product_name"].astype(str).to_dict()
        )

    baskets = df.groupby("order_id")["product_id"].apply(lambda s: frozenset(s)).tolist()
    n_orders = len(baskets)
    multi = [b for b in baskets if len(b) >= 2]
    n_multi = len(multi)

    # Per-product frequency
    item_counts: Counter[str] = Counter()
    for b in baskets:
        item_counts.update(b)
    n_unique_products = len(item_counts)

    if n_multi == 0:
        return {
            "summary": {
                "n_orders": n_orders, "n_unique_products": n_unique_products,
                "n_multi_item_baskets": 0, "multi_item_pct": 0.0,
                "recommendations_built_for": 0,
            },
            "recommendations": [],
            "warning": "no multi-item baskets — recommendations require ≥2 items per order",
        }

    # Per-product co-occurrence map: {anchor → Counter({other → count})}
    co: dict[str, Counter[str]] = defaultdict(Counter)
    for b in multi:
        if len(b) > MAX_BASKET_FOR_PAIRS:
            continue
        items = sorted(b)
        for a, c in combinations(items, 2):
            co[a][c] += 1
            co[c][a] += 1

    # Build per-anchor recommendation lists (sorted by lift = confidence / P(other)).
    top_anchors = [pid for pid, _ in item_counts.most_common(TOP_PRODUCTS)]
    recommendations = []
    for anchor in top_anchors:
        if anchor not in co:
            continue
        recos = []
        anchor_freq = item_counts[anchor]
        for other, cnt in co[anchor].most_common(RECOS_PER_PRODUCT * 3):
            if cnt < MIN_PAIR_COUNT:
                continue
            confidence = cnt / anchor_freq
            prob_other = item_counts[other] / n_orders
            lift = confidence / prob_other if prob_other > 0 else 0.0
            recos.append({
                "product_id":     other,
                "name":           name_map.get(other),
                "co_occurrences": int(cnt),
                "confidence":     round(confidence, 4),
                "lift":           round(lift, 3),
            })
        recos.sort(key=lambda r: (r["lift"], r["confidence"]), reverse=True)
        recommendations.append({
            "anchor_product_id": anchor,
            "anchor_name":       name_map.get(anchor),
            "anchor_frequency":  int(anchor_freq),
            "recommendations":   recos[:RECOS_PER_PRODUCT],
        })

    return {
        "summary": {
            "n_orders":                n_orders,
            "n_unique_products":       n_unique_products,
            "n_multi_item_baskets":    n_multi,
            "multi_item_pct":          round(n_multi / n_orders * 100, 2),
            "recommendations_built_for": len(recommendations),
        },
        "recommendations": recommendations,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_orders": 0, "n_unique_products": 0,
            "n_multi_item_baskets": 0, "multi_item_pct": 0.0,
            "recommendations_built_for": 0,
        },
        "recommendations": [],
        "warning": warning,
    }
