"""A03 — Market Basket Analysis.

Association rules — which products are frequently bought together.
Uses order-level co-occurrence. Calculates support, confidence, lift.
"""

from itertools import combinations

import pandas as pd
from ._base import analytics_task, has_col


@analytics_task("A03_market_basket", "basket")
def run_market_basket(df, session, job_id):
    df = df.dropna(subset=["id", "product_id"])

    # Group products by order
    order_products = df.groupby("id")["product_id"].apply(set).reset_index()
    order_products.columns = ["order_id", "products"]

    total_orders = len(order_products)
    # Filter orders with 2+ products
    multi = order_products[order_products["products"].apply(len) >= 2]
    multi_count = len(multi)

    if multi_count == 0:
        return {
            "rules": [],
            "summary": {"total_orders": total_orders, "multi_product_orders": 0},
        }

    # Performance guard: keep only top 500 products by frequency
    all_products = df["product_id"].value_counts()
    if len(all_products) > 500:
        top_products = set(all_products.head(500).index)
        multi = multi.copy()
        multi["products"] = multi["products"].apply(lambda s: s & top_products)
        multi = multi[multi["products"].apply(len) >= 2]

    # Count individual product support
    product_support = {}
    for _, row in multi.iterrows():
        for p in row["products"]:
            product_support[p] = product_support.get(p, 0) + 1

    # Count pair co-occurrences
    pair_counts = {}
    for _, row in multi.iterrows():
        for pair in combinations(sorted(row["products"]), 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    # Calculate metrics and build rules
    rules = []
    for (a, b), count in pair_counts.items():
        support = count / total_orders
        conf_ab = count / product_support.get(a, 1)
        conf_ba = count / product_support.get(b, 1)
        supp_b = product_support.get(b, 1) / total_orders
        supp_a = product_support.get(a, 1) / total_orders
        lift_ab = conf_ab / supp_b if supp_b > 0 else 0
        lift_ba = conf_ba / supp_a if supp_a > 0 else 0

        # Add both directions, keep the higher confidence one
        if conf_ab >= conf_ba:
            rules.append({
                "antecedent": a,
                "consequent": b,
                "support": round(support, 4),
                "confidence": round(conf_ab, 4),
                "lift": round(lift_ab, 4),
                "count": count,
            })
        else:
            rules.append({
                "antecedent": b,
                "consequent": a,
                "support": round(support, 4),
                "confidence": round(conf_ba, 4),
                "lift": round(lift_ba, 4),
                "count": count,
            })

    # Sort by lift descending, take top 50
    rules.sort(key=lambda r: r["lift"], reverse=True)
    rules = rules[:50]

    return {
        "rules": rules,
        "summary": {
            "total_orders": total_orders,
            "multi_product_orders": multi_count,
            "unique_products_analyzed": len(product_support),
            "total_pairs_found": len(pair_counts),
        },
    }
