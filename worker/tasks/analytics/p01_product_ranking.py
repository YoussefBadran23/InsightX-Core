"""P01 — Product Revenue Ranking.

Top + bottom products by revenue, lighter than A09 (which has 5 different
rank dimensions). Used on the Products dashboard hero card.

Required columns:  product_id, total_amount
Optional:          product_name, category, net_amount, quantity, order_date
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int, fmt_money


QUESTION = "Which products are pulling their weight?"


TOP_N = 25
BOTTOM_N = 10


@register(
    key="P01_product_ranking",
    analysis_type="product",
    required_cols=["product_id", "total_amount"],
    optional_cols=["product_name", "category", "net_amount", "quantity", "order_date"],
    description="Top-N + Bottom-N products by revenue.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["product_id", amount_col])
    df = df[df[amount_col] >= 0]
    df["product_id"] = df["product_id"].astype(str)

    if df.empty:
        return _empty("no rows after coercion")

    has_qty = has_col(df, "quantity")
    if has_qty:
        df["quantity"] = coerce_numeric(df["quantity"]).fillna(0)

    name_map = {}
    cat_map = {}
    if has_col(df, "product_name"):
        name_map = df.dropna(subset=["product_name"]).drop_duplicates("product_id").set_index("product_id")["product_name"].astype(str).to_dict()
    if has_col(df, "category"):
        cat_map = df.dropna(subset=["category"]).drop_duplicates("product_id").set_index("product_id")["category"].astype(str).to_dict()

    agg_kwargs = {
        "revenue": (amount_col, "sum"),
        "orders":  (amount_col, "count"),
    }
    if has_qty:
        agg_kwargs["units"] = ("quantity", "sum")

    prod = df.groupby("product_id").agg(**agg_kwargs).reset_index()
    total_rev = float(prod["revenue"].sum())
    prod = prod.sort_values("revenue", ascending=False).reset_index(drop=True)
    prod["rank"] = prod.index + 1
    prod["rev_pct"] = (prod["revenue"] / total_rev * 100).round(3) if total_rev else 0.0
    prod["avg_order_value"] = (prod["revenue"] / prod["orders"]).round(2)

    def _to_rec(r: dict) -> dict[str, Any]:
        pid = str(r["product_id"])
        rec = {
            "rank":     int(r["rank"]),
            "product_id": pid,
            "name":     name_map.get(pid),
            "category": cat_map.get(pid),
            "revenue":  round(float(r["revenue"]), 2),
            "orders":   int(r["orders"]),
            "rev_pct":  float(r["rev_pct"]),
            "avg_order_value": float(r["avg_order_value"]),
        }
        if has_qty:
            rec["units"] = int(r["units"])
        return rec

    top    = [_to_rec(r) for r in prod.head(TOP_N).to_dict("records")]
    bottom = [_to_rec(r) for r in prod[prod["revenue"] > 0].nsmallest(BOTTOM_N, "revenue").to_dict("records")]

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    top_rev_share = round(sum(p["rev_pct"] for p in top[:10]), 1)
    n_products = int(len(prod))
    top_product = top[0] if top else None

    headline = build_headline(
        value=top_rev_share,
        label="revenue from top 10 products",
        period=f"{fmt_int(n_products)} products tracked",
    )

    bullets: list[str] = []
    if top_product:
        nm = top_product.get("name") or top_product.get("product_id")
        bullets.append(
            f"#1 product: {str(nm)[:40]} — {fmt_money(top_product['revenue'])} "
            f"({top_product['rev_pct']:.1f}% of revenue) across {top_product['orders']} orders."
        )
    else:
        bullets.append(f"Tracking {fmt_int(n_products)} products in total.")

    if top_rev_share >= 70:
        bullets.append(
            f"Highly concentrated: top 10 products = {top_rev_share:.0f}% of revenue. "
            f"Lose stock on any of these and revenue takes a hit."
        )
    elif top_rev_share >= 40:
        bullets.append(
            f"Top 10 carry {top_rev_share:.0f}% — typical 80/20 distribution. "
            f"Reorder top SKUs aggressively and let the long tail follow."
        )
    else:
        bullets.append(
            f"Well-distributed: top 10 only {top_rev_share:.0f}% of revenue. "
            f"Many products contribute meaningfully — broad catalog strategy is working."
        )

    if bottom:
        n_low = sum(1 for b in bottom if b["revenue"] < (top_product["revenue"] * 0.01 if top_product else 0))
        if n_low >= 3:
            bullets.append(
                f"{n_low} products earn less than 1% of your top product — "
                f"consider delisting or bundling them to cut SKU complexity."
            )
        else:
            bullets.append(
                "Long-tail products are still earning — keep them around but "
                "don't reorder if velocity is too low."
            )
    else:
        bullets.append(
            "Track which products underperform vs your top 5 — kill the deadweight "
            "and you free up cash for hot SKUs."
        )

    actions = [
        action("View product catalog", kind="primary",
               deeplink="/dashboard/products", icon="arrow"),
        action("Export ranking CSV", kind="secondary", deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary": {
            "n_products":   int(len(prod)),
            "total_revenue": round(total_rev, 2),
            "top_rev_share": round(sum(p["rev_pct"] for p in top[:10]), 2),
        },
        "top_products":    top,
        "bottom_products": bottom,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="revenue from top products", period="no data"),
            fallback_bullets=[
                "No product data yet — needs product_id + revenue per order.",
                "Once data exists, this card ranks every product by revenue and shows top/bottom performers.",
                "Knowing which products pull their weight is foundational — reorder the winners, kill the duds.",
            ],
            suggested_actions=[
                action("Upload data", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {"n_products": 0, "total_revenue": 0.0, "top_rev_share": 0.0},
        "top_products": [], "bottom_products": [],
        "warning": warning,
    }
