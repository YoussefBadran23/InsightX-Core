"""A12 — Discount Impact Analysis.

How much revenue is given away in discounts, where it lands, and whether
discounted orders behave differently from full-price orders.

Output framing
--------------
- Headline: total discount $, % of gross, % of orders that used a discount
- Comparison: AOV / order count for discounted vs non-discounted orders
- Distribution: discount-percent buckets (0-5%, 5-10%, …, 50%+)
- Drilldowns: top products/categories receiving the heaviest discounts

A note on "lift"
----------------
We deliberately do *not* claim a causal "discounts caused +X% revenue" number.
That requires either a controlled experiment or an uplift model (which lives
in A15/A23). What we *can* report:

- AOV ratio (discounted vs non-discounted)
- The discounted-order share of total revenue

…both of which let an operator judge whether the discount program looks
healthy without overclaiming.

Required columns:  discount_amount, total_amount
Optional columns:  net_amount, order_id, order_date, product_id, product_name,
                   category, customer_id, quantity

Output schema::

    {
      "summary": {
        "n_orders":              int,
        "total_gross_revenue":   float,
        "total_discount":        float,
        "discount_pct_of_gross": float,
        "n_discounted":          int,
        "n_full_price":          int,
        "discounted_pct":        float,
        "avg_discount_amount":   float,
        "avg_discount_pct":      float
      },
      "comparison": {
        "discounted":   {"orders": int, "revenue": float, "aov": float,
                         "discount": float, "avg_discount_pct": float},
        "full_price":   {"orders": int, "revenue": float, "aov": float},
        "aov_ratio":    float    # discounted_aov / full_price_aov
      },
      "distribution": [
        {"bucket": "0-5%", "orders": int, "discount": float,
         "avg_order_value": float, "pct_of_orders": float}
      ],
      "by_category":  [...] | null,
      "top_discounted_products": [...] | null,
      "monthly_trend": [...] | null,
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


DISCOUNT_BUCKETS = [
    (0, 5,    "0-5%"),
    (5, 10,   "5-10%"),
    (10, 25,  "10-25%"),
    (25, 50,  "25-50%"),
    (50, 100, "50-100%"),
]


@register(
    key="A12_discount_impact",
    analysis_type="revenue",
    required_cols=["discount_amount", "total_amount"],
    optional_cols=["net_amount", "order_id", "order_date", "product_id",
                   "product_name", "category", "customer_id", "quantity"],
    description="Discount usage, AOV impact, and tier distribution.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    df["discount_amount"] = coerce_numeric(df["discount_amount"]).fillna(0)
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])

    df = df.dropna(subset=["total_amount"])
    df = df[df["total_amount"] > 0]
    # Discount must be non-negative; clip negative noise to zero.
    df["discount_amount"] = df["discount_amount"].clip(lower=0)
    # Discounts greater than the gross are nonsensical; cap at gross to avoid
    # generating negative net_amounts that would corrupt downstream stats.
    df["discount_amount"] = df[["discount_amount", "total_amount"]].min(axis=1)

    if df.empty:
        return {
            "summary": {
                "n_orders": 0, "total_gross_revenue": 0.0, "total_discount": 0.0,
                "discount_pct_of_gross": 0.0, "n_discounted": 0,
                "n_full_price": 0, "discounted_pct": 0.0,
                "avg_discount_amount": 0.0, "avg_discount_pct": 0.0,
            },
            "comparison": None, "distribution": [],
            "by_category": None, "top_discounted_products": None,
            "monthly_trend": None,
            "warning": "no rows with valid total_amount after coercion",
        }

    df["_discount_pct"] = (df["discount_amount"] / df["total_amount"] * 100).round(4)

    n_orders = int(len(df))
    gross = float(df["total_amount"].sum())
    total_disc = float(df["discount_amount"].sum())

    is_disc = df["discount_amount"] > 0
    n_disc = int(is_disc.sum())
    n_full = n_orders - n_disc

    # ── Headline numbers ────────────────────────────────────────────────────
    summary = {
        "n_orders": n_orders,
        "total_gross_revenue": round(gross, 2),
        "total_discount": round(total_disc, 2),
        "discount_pct_of_gross": round(total_disc / gross * 100, 2) if gross > 0 else 0.0,
        "n_discounted": n_disc,
        "n_full_price": n_full,
        "discounted_pct": round(n_disc / n_orders * 100, 2),
        "avg_discount_amount": round(float(df.loc[is_disc, "discount_amount"].mean()), 2)
            if n_disc > 0 else 0.0,
        "avg_discount_pct": round(float(df.loc[is_disc, "_discount_pct"].mean()), 2)
            if n_disc > 0 else 0.0,
    }

    # ── Discounted vs full-price comparison ─────────────────────────────────
    disc_rev = float(df.loc[is_disc, "total_amount"].sum())
    full_rev = float(df.loc[~is_disc, "total_amount"].sum())
    disc_aov = disc_rev / n_disc if n_disc > 0 else 0.0
    full_aov = full_rev / n_full if n_full > 0 else 0.0
    comparison = {
        "discounted": {
            "orders": n_disc,
            "revenue": round(disc_rev, 2),
            "aov": round(disc_aov, 2),
            "discount": round(total_disc, 2),
            "avg_discount_pct": summary["avg_discount_pct"],
        },
        "full_price": {
            "orders": n_full,
            "revenue": round(full_rev, 2),
            "aov": round(full_aov, 2),
        },
        "aov_ratio": round(disc_aov / full_aov, 3) if full_aov > 0 else 0.0,
    }

    # ── Bucketed distribution ───────────────────────────────────────────────
    distribution: list[dict[str, Any]] = []
    for lo, hi, label in DISCOUNT_BUCKETS:
        mask = (df["_discount_pct"] >= lo) & (df["_discount_pct"] < hi)
        n_bucket = int(mask.sum())
        if n_bucket == 0:
            distribution.append({
                "bucket": label, "orders": 0, "discount": 0.0,
                "revenue": 0.0, "avg_order_value": 0.0,
                "pct_of_orders": 0.0,
            })
            continue
        bucket_rev = float(df.loc[mask, "total_amount"].sum())
        bucket_disc = float(df.loc[mask, "discount_amount"].sum())
        distribution.append({
            "bucket": label,
            "orders": n_bucket,
            "discount": round(bucket_disc, 2),
            "revenue": round(bucket_rev, 2),
            "avg_order_value": round(bucket_rev / n_bucket, 2),
            "pct_of_orders": round(n_bucket / n_orders * 100, 2),
        })

    # ── Per-category drilldown ──────────────────────────────────────────────
    by_category = None
    if has_col(df, "category"):
        sub = df.dropna(subset=["category"]).copy()
        if not sub.empty:
            sub["category"] = sub["category"].astype(str)
            cat_agg = (
                sub.groupby("category")
                   .agg(orders=("total_amount", "count"),
                        gross=("total_amount", "sum"),
                        discount=("discount_amount", "sum"))
                   .reset_index()
            )
            cat_agg["discount_pct"] = (cat_agg["discount"] / cat_agg["gross"] * 100).round(2)
            cat_agg = cat_agg.sort_values("discount", ascending=False)
            by_category = [
                {
                    "category": str(r["category"]),
                    "orders": int(r["orders"]),
                    "gross": round(float(r["gross"]), 2),
                    "discount": round(float(r["discount"]), 2),
                    "discount_pct": float(r["discount_pct"]) if pd.notna(r["discount_pct"]) else 0.0,
                }
                for r in cat_agg.head(20).to_dict("records")
            ]

    # ── Top discounted products ─────────────────────────────────────────────
    top_discounted_products = None
    if has_col(df, "product_id"):
        sub = df.dropna(subset=["product_id"]).copy()
        sub = sub[sub["discount_amount"] > 0]
        if not sub.empty:
            sub["product_id"] = sub["product_id"].astype(str)
            name_map: dict[str, str] = {}
            if has_col(sub, "product_name"):
                name_map = (
                    sub.dropna(subset=["product_name"])
                       .drop_duplicates(subset="product_id")
                       .set_index("product_id")["product_name"].astype(str).to_dict()
                )
            prod_agg = (
                sub.groupby("product_id")
                   .agg(orders=("total_amount", "count"),
                        gross=("total_amount", "sum"),
                        discount=("discount_amount", "sum"))
                   .reset_index()
            )
            prod_agg["avg_disc_pct"] = (prod_agg["discount"] / prod_agg["gross"] * 100).round(2)
            prod_agg = prod_agg.sort_values("discount", ascending=False).head(15)
            top_discounted_products = [
                {
                    "product_id": str(r["product_id"]),
                    "name": name_map.get(str(r["product_id"])),
                    "orders": int(r["orders"]),
                    "gross": round(float(r["gross"]), 2),
                    "discount": round(float(r["discount"]), 2),
                    "avg_discount_pct": float(r["avg_disc_pct"]) if pd.notna(r["avg_disc_pct"]) else 0.0,
                }
                for r in prod_agg.to_dict("records")
            ]

    # ── Monthly trend ───────────────────────────────────────────────────────
    monthly_trend = None
    if has_col(df, "order_date"):
        sub = df.copy()
        sub["order_date"] = coerce_date(sub["order_date"])
        sub = sub.dropna(subset=["order_date"])
        if not sub.empty:
            sub["_period"] = sub["order_date"].dt.to_period("M").astype(str)
            tg = sub.groupby("_period").agg(
                orders=("total_amount", "count"),
                gross=("total_amount", "sum"),
                discount=("discount_amount", "sum"),
                n_disc=("discount_amount", lambda s: int((s > 0).sum())),
            ).reset_index().sort_values("_period")
            tg["discount_pct"] = (tg["discount"] / tg["gross"] * 100).round(2)
            tg["disc_share"] = (tg["n_disc"] / tg["orders"] * 100).round(2)
            monthly_trend = [
                {"period": r["_period"],
                 "orders": int(r["orders"]),
                 "gross": round(float(r["gross"]), 2),
                 "discount": round(float(r["discount"]), 2),
                 "discount_pct": float(r["discount_pct"]) if pd.notna(r["discount_pct"]) else 0.0,
                 "discounted_orders_pct": float(r["disc_share"])}
                for r in tg.to_dict("records")
            ]

    return {
        "summary": summary,
        "comparison": comparison,
        "distribution": distribution,
        "by_category": by_category,
        "top_discounted_products": top_discounted_products,
        "monthly_trend": monthly_trend,
        "warning": None,
    }
