"""A03 — Market Basket Analysis (Optimized)."""
from itertools import combinations
import pandas as pd
from ._base import analytics_task

COLS = ["id", "product_id"]

@analytics_task("A03_market_basket", "basket", required_cols=COLS)
def run_market_basket(df, session, job_id):
    df = df.dropna(subset=["id", "product_id"])

    # Performance Guard: Focus on top 500 products
    top_500 = df["product_id"].value_counts().head(500).index
    df = df[df["product_id"].isin(top_500)]

    # Group by order
    order_groups = df.groupby("id")["product_id"].apply(list)
    order_groups = order_groups[order_groups.map(len).between(2, 50)] # Skip small and giant orders
    
    total_orders = len(order_groups)
    if total_orders == 0: return {"rules": []}

    pair_counts = {}
    product_support = {}

    for products in order_groups:
        unique_prods = set(products)
        for p in unique_prods:
            product_support[p] = product_support.get(p, 0) + 1
        
        for pair in combinations(sorted(unique_prods), 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    rules = []
    for (a, b), count in pair_counts.items():
        support = count / total_orders
        conf = count / product_support[a]
        lift = conf / (product_support[b] / total_orders)
        
        if lift > 1.1:
            rules.append({
                "antecedent": a, "consequent": b,
                "support": round(support, 4), "confidence": round(conf, 4),
                "lift": round(lift, 4), "count": count
            })

    return {
        "rules": sorted(rules, key=lambda x: x["lift"], reverse=True)[:50],
        "summary": {"total_orders": total_orders, "unique_products": len(product_support)}
    }