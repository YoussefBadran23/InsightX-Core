"""P02 — Category Performance.

Revenue + order share by category, optionally split by subcategory and with
a monthly trend per category.

Required columns:  category, total_amount
Optional:          subcategory, order_date, net_amount, quantity, product_id
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int, fmt_money


QUESTION = "Which categories are pulling the most weight?"


@register(
    key="P02_category_performance",
    analysis_type="product",
    required_cols=["category", "total_amount"],
    optional_cols=["subcategory", "order_date", "net_amount", "quantity", "product_id"],
    description="Revenue + orders by product category, with subcategory + monthly trend.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["category", amount_col])
    df = df[df[amount_col] >= 0]
    df["category"] = df["category"].astype(str)

    if df.empty:
        return _empty("no rows after coercion")

    has_qty = has_col(df, "quantity")
    if has_qty:
        df["quantity"] = coerce_numeric(df["quantity"]).fillna(0)

    agg_kwargs = {"revenue": (amount_col, "sum"), "orders": (amount_col, "count")}
    if has_qty:
        agg_kwargs["units"] = ("quantity", "sum")
    if has_col(df, "product_id"):
        df["product_id"] = df["product_id"].astype(str)
        agg_kwargs["unique_products"] = ("product_id", "nunique")

    cat = df.groupby("category").agg(**agg_kwargs).reset_index()
    total_rev = float(cat["revenue"].sum())
    cat = cat.sort_values("revenue", ascending=False).reset_index(drop=True)
    cat["rank"]    = cat.index + 1
    cat["rev_pct"] = (cat["revenue"] / total_rev * 100).round(2) if total_rev else 0.0
    cat["aov"]     = (cat["revenue"] / cat["orders"]).round(2)

    by_category = []
    for r in cat.to_dict("records"):
        rec: dict[str, Any] = {
            "category": str(r["category"]),
            "rank":     int(r["rank"]),
            "revenue":  round(float(r["revenue"]), 2),
            "orders":   int(r["orders"]),
            "rev_pct":  float(r["rev_pct"]),
            "aov":      float(r["aov"]),
        }
        if has_qty:
            rec["units"] = int(r["units"])
        if "unique_products" in r:
            rec["unique_products"] = int(r["unique_products"])
        by_category.append(rec)

    # ── Subcategory rollup ──────────────────────────────────────────────────
    by_subcategory = None
    if has_col(df, "subcategory"):
        sub = df.dropna(subset=["subcategory"]).copy()
        sub["subcategory"] = sub["subcategory"].astype(str)
        sub_g = sub.groupby(["category", "subcategory"]).agg(
            revenue=(amount_col, "sum"),
            orders=(amount_col, "count"),
        ).reset_index().sort_values("revenue", ascending=False)
        by_subcategory = [
            {
                "category":    str(r["category"]),
                "subcategory": str(r["subcategory"]),
                "revenue":     round(float(r["revenue"]), 2),
                "orders":      int(r["orders"]),
            }
            for r in sub_g.head(50).to_dict("records")
        ]

    # ── Monthly trend per top-5 category ────────────────────────────────────
    monthly_trend = None
    if has_col(df, "order_date"):
        sub = df.copy()
        sub["order_date"] = coerce_date(sub["order_date"])
        sub = sub.dropna(subset=["order_date"])
        top_5_cats = [c["category"] for c in by_category[:5]]
        sub = sub[sub["category"].isin(top_5_cats)]
        if not sub.empty:
            sub["_period"] = sub["order_date"].dt.to_period("M").astype(str)
            trend = sub.groupby(["_period", "category"])[amount_col].sum().reset_index()
            trend = trend.sort_values(["_period", "category"])
            monthly_trend = [
                {
                    "period":   r["_period"],
                    "category": str(r["category"]),
                    "revenue":  round(float(r[amount_col]), 2),
                }
                for r in trend.to_dict("records")
            ]

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    top_cat = by_category[0] if by_category else None
    top_3_share = round(sum(c["rev_pct"] for c in by_category[:3]), 2)
    n_categories = int(len(by_category))

    headline = build_headline(
        value=round(top_cat["revenue"], 2) if top_cat else 0,
        label=(f"{top_cat['category']} · {top_cat['rev_pct']:.0f}% of revenue"
               if top_cat else "category revenue"),
        period=f"{n_categories} categories · {fmt_money(total_rev)} total",
    )

    bullets: list[str] = []
    # 1 — Top category callout
    if top_cat:
        bullets.append(
            f"{top_cat['category']} earns {fmt_money(top_cat['revenue'])} "
            f"({top_cat['rev_pct']:.0f}% of revenue) · "
            f"AOV {fmt_money(top_cat['aov'])} across {fmt_int(top_cat['orders'])} orders."
        )

    # 2 — Concentration framing
    if top_3_share >= 75:
        bullets.append(
            f"Top 3 categories = {top_3_share:.0f}% of revenue. "
            f"High concentration: lose one and revenue takes a real hit."
        )
    elif top_3_share >= 50:
        bullets.append(
            f"Top 3 categories = {top_3_share:.0f}% of revenue — "
            f"a balanced portfolio with meaningful diversification."
        )
    else:
        bullets.append(
            f"Revenue is spread thin: top 3 categories only {top_3_share:.0f}%. "
            f"Strong long-tail diversification."
        )

    # 3 — Long-tail or growth recommendation
    if n_categories >= 5:
        bottom = by_category[-1]
        if bottom["rev_pct"] < 1:
            bullets.append(
                f"{bottom['category']} earns under 1% of revenue ({fmt_money(bottom['revenue'])}) — "
                f"consider rebalancing assortment or marketing toward winners."
            )
        else:
            bullets.append(
                f"Even your smallest category ({bottom['category']}) brings "
                f"{fmt_money(bottom['revenue'])} — every shelf is contributing."
            )
    else:
        bullets.append(
            "Few categories means each one matters more — diversify before "
            "any single category dictates your business."
        )

    actions = [
        action("Inspect top category", kind="primary",
               deeplink=f"/dashboard/products?category={top_cat['category']}" if top_cat else "/dashboard/products",
               icon="arrow"),
        action("Compare all categories", kind="info",
               deeplink="/dashboard/analytics?focus=P02", icon="arrow"),
        action("Export category report", kind="secondary",
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
            "n_categories":  n_categories,
            "total_revenue": round(total_rev, 2),
            "top_category":  top_cat,
            "top_3_share":   top_3_share,
        },
        "by_category":    by_category,
        "by_subcategory": by_subcategory,
        "monthly_trend":  monthly_trend,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="category revenue", period="no data"),
            fallback_bullets=[
                "No category data yet — needs a category column + revenue tagged "
                "on each order.",
                "Once available, this card ranks categories by revenue and "
                "shows where your concentration risk lives.",
                "Knowing your top category lets you double down on what works "
                "instead of spreading marketing thin.",
            ],
            suggested_actions=[
                action("Check upload mapping", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {"n_categories": 0, "total_revenue": 0.0, "top_category": None, "top_3_share": 0.0},
        "by_category": [], "by_subcategory": None, "monthly_trend": None,
        "warning": warning,
    }
