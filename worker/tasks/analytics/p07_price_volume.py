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
from ._contract import action, build_headline, build_payload, fmt_int, fmt_money


QUESTION = "How does my pricing affect what customers buy?"


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

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    n_products = int(len(prod))
    avg_price = round(float(prod["avg_unit_price"].mean()), 2)
    median_price = round(float(prod["avg_unit_price"].median()), 2)

    headline = build_headline(
        value=round(elasticity, 3) if elasticity is not None else 0,
        label=(
            "elasticity coefficient · price vs volume"
            if elasticity is not None
            else "price vs volume analysis"
        ),
        period=f"{fmt_int(n_products)} products",
    )

    bullets: list[str] = []
    # 1 — Elasticity interpretation
    if elasticity is None:
        bullets.append(
            "Not enough price variance across products to estimate elasticity — "
            "need wider price ranges or more SKUs for a reliable signal."
        )
    elif elasticity < -0.3:
        bullets.append(
            f"Classic demand curve: r = {elasticity:+.2f}. Higher-priced products sell "
            f"fewer units — customers are price-sensitive here."
        )
    elif elasticity > 0.3:
        bullets.append(
            f"Counter-intuitive: r = {elasticity:+.2f}. Higher prices coincide with "
            f"higher volume — likely premium/luxury positioning at play."
        )
    else:
        bullets.append(
            f"Weak link between price and volume (r = {elasticity:+.2f}) — pricing "
            f"isn't your main demand lever; product mix matters more."
        )

    # 2 — Price range
    bullets.append(
        f"Avg unit price: {fmt_money(avg_price)} · median: {fmt_money(median_price)}. "
        + (f"Wide spread suggests range positioning."
           if avg_price > median_price * 1.3
           else "Tight spread — uniform pricing across catalog.")
    )

    # 3 — Top performer or recommendation
    if products:
        top = products[0]
        rev_label = (f" · {fmt_money(top['total_revenue'])} revenue"
                     if "total_revenue" in top else "")
        bullets.append(
            f"Top performer: {top.get('name') or top['product_id'][:18]} at "
            f"{fmt_money(top['avg_unit_price'])} · {fmt_int(top['total_units'])} units{rev_label}."
        )

    actions = [
        action("Explore price-volume scatter", kind="primary",
               deeplink="/dashboard/products?focus=P07", icon="arrow"),
    ]
    if elasticity is not None and elasticity < -0.3:
        actions.append(action(
            "Test a price-elasticity experiment", kind="info",
            deeplink="/dashboard/products?action=price-test", icon="arrow",
        ))
    actions.append(action(
        "Export pricing report", kind="secondary", deeplink=None, icon="download",
    ))

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions[:3],
        ),
        "summary": {
            "n_products":           n_products,
            "elasticity_correlation": round(elasticity, 4) if elasticity is not None else None,
            "elasticity_interpretation": _interpret_elasticity(elasticity),
            "avg_unit_price":       avg_price,
            "median_unit_price":    median_price,
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
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="price-volume analysis",
                                    period="no data"),
            fallback_bullets=[
                "No pricing data yet — need product_id + unit_price + quantity "
                "columns on your upload.",
                "Once available, this card estimates price elasticity and surfaces "
                "the products where pricing moves the needle most.",
                "Price elasticity guides your discount strategy — elastic products "
                "respond to promos, inelastic ones don't.",
            ],
            suggested_actions=[
                action("Check upload mapping", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {
            "n_products": 0, "elasticity_correlation": None,
            "elasticity_interpretation": "no data",
            "avg_unit_price": 0.0, "median_unit_price": 0.0,
        },
        "products": [],
        "warning": warning,
    }
