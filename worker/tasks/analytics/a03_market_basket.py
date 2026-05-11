"""A03 — Market Basket Analysis.

Finds products frequently bought together by computing classic association-rule
metrics on basket data:

- **Support(A∩B)**:  P(A and B in same basket) = co-occurrences / total baskets
- **Confidence(A→B)**: P(B | A) = co-occurrences / baskets-containing-A
- **Lift(A,B)**:    confidence(A→B) / P(B). >1 means positive association.

Why we don't pull in `mlxtend.apriori`
--------------------------------------
For the dataset sizes we ship (5K–50K orders, a few thousand products) brute-
force pair counting in pandas is fast enough and avoids a heavy dependency.
We cap basket size when generating pairs to prevent the combinatorial explosion
on rare bulk orders (a 100-item basket would emit 4,950 pairs alone).

Required columns:  order_id, product_id
Optional columns:  product_name (for human-readable output), quantity

Output schema::

    {
      "summary": {
        "n_orders": int,
        "n_unique_products": int,
        "n_multi_item_baskets": int,
        "multi_item_pct": float,
        "avg_basket_size": float,
        "max_basket_size": int
      },
      "top_products": [{"product_id": str, "name": str|None,
                        "frequency": int, "support": float}],
      "top_pairs": [
        {"antecedent": str, "consequent": str,
         "antecedent_name": str|None, "consequent_name": str|None,
         "co_occurrences": int, "support": float,
         "confidence": float, "lift": float}
      ],
      "top_triples": [{"items": [str, str, str], "co_occurrences": int,
                       "support": float}],
      "warning": str | None
    }
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

import pandas as pd

from ._base import has_col, register


# Tunables. Threshold scales off `n_multi` (multi-item baskets) rather than
# total orders, because pairs can only come from those baskets — datasets like
# Olist where 97% of orders are single-item would otherwise produce zero rules.
MIN_PAIR_SUPPORT_OF_MULTI = 0.0015  # pair must appear in ≥0.15% of multi-baskets
PAIR_COUNT_FLOOR = 2               # absolute minimum (statistical sanity)
MAX_BASKET_FOR_PAIRS = 30          # skip oversized baskets when generating pairs
TOP_N_PAIRS = 25
TOP_N_PRODUCTS = 20
TOP_N_TRIPLES = 10


@register(
    key="A03_market_basket",
    analysis_type="product",
    required_cols=["order_id", "product_id"],
    optional_cols=["product_name", "quantity"],
    description="Items frequently bought together (support, confidence, lift).",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["order_id", "product_id"])
    df["order_id"] = df["order_id"].astype(str)
    df["product_id"] = df["product_id"].astype(str)

    # Build product_id → display name map for nicer output.
    name_map: dict[str, str] = {}
    if has_col(df, "product_name"):
        name_map = (
            df.dropna(subset=["product_name"])
              .drop_duplicates(subset="product_id")
              .set_index("product_id")["product_name"].astype(str).to_dict()
        )

    # ── Build baskets ───────────────────────────────────────────────────────
    # A basket is the set of distinct products in one order. Quantity-weighting
    # would distort co-occurrence (a single buyer of 50 of one item should not
    # outweigh 50 buyers of 1 each).
    baskets = (
        df.groupby("order_id")["product_id"]
          .apply(lambda s: frozenset(s))
          .tolist()
    )
    n_orders = len(baskets)

    if n_orders == 0:
        return {
            "summary": {"n_orders": 0, "n_unique_products": 0,
                        "n_multi_item_baskets": 0, "multi_item_pct": 0.0,
                        "avg_basket_size": 0.0, "max_basket_size": 0},
            "top_products": [], "top_pairs": [], "top_triples": [],
            "warning": "no orders found",
        }

    sizes = [len(b) for b in baskets]
    multi = [b for b in baskets if len(b) >= 2]
    n_multi = len(multi)

    # ── Single-item supports ────────────────────────────────────────────────
    item_counts: Counter[str] = Counter()
    for b in baskets:
        item_counts.update(b)

    top_products = [
        {
            "product_id": pid,
            "name": name_map.get(pid),
            "frequency": int(cnt),
            "support": round(cnt / n_orders, 4),
        }
        for pid, cnt in item_counts.most_common(TOP_N_PRODUCTS)
    ]

    # ── Pair counts ─────────────────────────────────────────────────────────
    # Skip oversized baskets to bound runtime. Sort items inside each pair so
    # (A,B) and (B,A) collapse to one key.
    pair_counts: Counter[tuple[str, str]] = Counter()
    for b in multi:
        if len(b) > MAX_BASKET_FOR_PAIRS:
            continue
        for a, c in combinations(sorted(b), 2):
            pair_counts[(a, c)] += 1

    if not pair_counts:
        warning = (
            f"no co-occurring pairs found — only {n_multi}/{n_orders} "
            f"({n_multi / n_orders * 100:.1f}%) baskets have ≥2 items"
        )
        return {
            "summary": {
                "n_orders": int(n_orders),
                "n_unique_products": int(len(item_counts)),
                "n_multi_item_baskets": int(n_multi),
                "multi_item_pct": round(n_multi / n_orders * 100, 2),
                "avg_basket_size": round(sum(sizes) / n_orders, 3),
                "max_basket_size": int(max(sizes)),
            },
            "top_products": top_products,
            "top_pairs": [], "top_triples": [],
            "warning": warning,
        }

    min_pair_count = max(PAIR_COUNT_FLOOR, int(MIN_PAIR_SUPPORT_OF_MULTI * n_multi))

    pair_rules: list[dict[str, Any]] = []
    for (a, c), cnt in pair_counts.items():
        if cnt < min_pair_count:
            continue
        support_ab = cnt / n_orders
        # Two directions: A→B and B→A. We emit the higher-confidence direction
        # so the rule is in its most informative form.
        conf_ab = cnt / item_counts[a]
        conf_ba = cnt / item_counts[c]
        if conf_ab >= conf_ba:
            ant, con, conf = a, c, conf_ab
        else:
            ant, con, conf = c, a, conf_ba
        prob_con = item_counts[con] / n_orders
        lift = conf / prob_con if prob_con > 0 else 0.0
        pair_rules.append({
            "antecedent": ant,
            "consequent": con,
            "antecedent_name": name_map.get(ant),
            "consequent_name": name_map.get(con),
            "co_occurrences": int(cnt),
            "support": round(support_ab, 4),
            "confidence": round(conf, 4),
            "lift": round(lift, 3),
        })

    pair_rules.sort(key=lambda r: (r["lift"], r["support"]), reverse=True)
    pair_rules = pair_rules[:TOP_N_PAIRS]

    # ── Optional triples (only if pairs are dense) ──────────────────────────
    # Triples explode quickly so we only attempt them when there's signal.
    triples_out: list[dict[str, Any]] = []
    if n_multi >= 50 and len(pair_counts) >= 20:
        triple_counts: Counter[tuple[str, str, str]] = Counter()
        min_triple_count = max(PAIR_COUNT_FLOOR, int(MIN_PAIR_SUPPORT_OF_MULTI * n_multi))
        for b in multi:
            if len(b) < 3 or len(b) > MAX_BASKET_FOR_PAIRS:
                continue
            for trio in combinations(sorted(b), 3):
                triple_counts[trio] += 1
        triples_filtered = [
            (trio, cnt) for trio, cnt in triple_counts.items() if cnt >= min_triple_count
        ]
        triples_filtered.sort(key=lambda x: x[1], reverse=True)
        for trio, cnt in triples_filtered[:TOP_N_TRIPLES]:
            triples_out.append({
                "items": list(trio),
                "names": [name_map.get(p) for p in trio],
                "co_occurrences": int(cnt),
                "support": round(cnt / n_orders, 4),
            })

    return {
        "summary": {
            "n_orders": int(n_orders),
            "n_unique_products": int(len(item_counts)),
            "n_multi_item_baskets": int(n_multi),
            "multi_item_pct": round(n_multi / n_orders * 100, 2),
            "avg_basket_size": round(sum(sizes) / n_orders, 3),
            "max_basket_size": int(max(sizes)),
        },
        "top_products": top_products,
        "top_pairs": pair_rules,
        "top_triples": triples_out,
        "warning": None,
    }
