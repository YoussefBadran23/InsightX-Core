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
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "What should I cross-sell next to each product?"


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

    baskets = df.groupby("order_id")["product_id"].agg(frozenset).tolist()
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
            **build_payload(
                question=QUESTION,
                headline=build_headline(value=0, label="cross-sell pairs built",
                                        period=f"{fmt_int(n_orders)} orders"),
                fallback_bullets=[
                    "Every order in your data contains only one product — there "
                    "are no co-purchase patterns to learn from.",
                    "If you sell bundles or your POS splits multi-item carts into "
                    "separate orders, check that order_id is preserved across line items.",
                    "Multi-item baskets are the highest-margin lever in retail — "
                    "even 10% multi-item lift typically beats most ads.",
                ],
                suggested_actions=[
                    action("Check upload mapping", kind="primary",
                           deeplink="/dashboard/upload", icon="arrow"),
                ],
            ),
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

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    multi_item_pct = round(n_multi / n_orders * 100, 2)
    headline = build_headline(
        value=int(len(recommendations)),
        label="products with cross-sell pairs ready",
        period=f"{fmt_int(n_multi)} multi-item orders",
    )

    bullets: list[str] = []
    bullets.append(
        f"Built bundles for {fmt_int(len(recommendations))} top products from "
        f"{fmt_int(n_multi)} multi-item orders ({multi_item_pct:.0f}% of total)."
    )

    # Highlight strongest pair
    if recommendations:
        anchor = recommendations[0]
        top_pair = anchor["recommendations"][0] if anchor["recommendations"] else None
        if top_pair and top_pair["lift"] > 1:
            anchor_name = anchor.get("anchor_name") or anchor["anchor_product_id"][:16]
            pair_name = top_pair.get("name") or top_pair["product_id"][:16]
            bullets.append(
                f"Strongest pair: customers who buy {anchor_name} are "
                f"{top_pair['lift']:.1f}× more likely to also buy {pair_name}."
            )
        else:
            bullets.append(
                "Co-occurrence is mostly random — your customers shop one item at a time. "
                "Promo bundles can change that."
            )

    if multi_item_pct < 20:
        bullets.append(
            f"Only {multi_item_pct:.0f}% of orders contain multiple items — huge upside "
            f"in 'frequently bought together' widgets and post-purchase upsells."
        )
    else:
        bullets.append(
            f"{multi_item_pct:.0f}% of orders are multi-item — your cross-sell is already "
            f"working. Use these recommendations to push it higher."
        )

    actions = [
        action("View bundle suggestions", kind="primary",
               deeplink="/dashboard/products?focus=A24", icon="arrow"),
        action("Add to product page widget", kind="positive",
               deeplink="/dashboard/products?action=widget", icon="arrow"),
        action("Export recommendations CSV", kind="secondary",
               deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary": {
            "n_orders":                n_orders,
            "n_unique_products":       n_unique_products,
            "n_multi_item_baskets":    n_multi,
            "multi_item_pct":          multi_item_pct,
            "recommendations_built_for": len(recommendations),
        },
        "recommendations": recommendations,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="cross-sell pairs built", period="no data"),
            fallback_bullets=[
                "No order data yet — basket recommendations need order_id + "
                "product_id columns on your upload.",
                "Once available, this card surfaces 'frequently bought together' "
                "pairs ranked by lift (how much more likely than random).",
                "Bundle recommendations are the highest-ROI cross-sell tool — "
                "Amazon's whole revenue line is built on it.",
            ],
            suggested_actions=[
                action("Check upload mapping", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {
            "n_orders": 0, "n_unique_products": 0,
            "n_multi_item_baskets": 0, "multi_item_pct": 0.0,
            "recommendations_built_for": 0,
        },
        "recommendations": [],
        "warning": warning,
    }
