"""A21 — Return Rate Analysis.

Per-product and per-category return rate from the boolean `return_flag` column.
Surfaces:
- Overall return rate %
- Top return-offender products (sorted by return_rate among products with N≥5 orders)
- By-category aggregates
- Distribution of products by return-rate bucket
- Monthly trend (if order_date is present)

Required columns:  return_flag, product_id
Optional columns:  total_amount, category, product_name, order_date
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int, fmt_money


QUESTION = "What's coming back to me — and which products are the biggest offenders?"


MIN_ORDERS_FOR_RANK = 5
TOP_N = 20

RETURN_RATE_BUCKETS = [
    (0.0,  0.01, "0%"),
    (0.01, 0.05, "0-5%"),
    (0.05, 0.15, "5-15%"),
    (0.15, 0.30, "15-30%"),
    (0.30, 1.01, "30%+"),
]


def _coerce_return_flag(s: pd.Series) -> pd.Series:
    """Coerce return_flag column to bool, handling string/numeric variants."""
    if pd.api.types.is_bool_dtype(s):
        return s.astype(bool)
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float).fillna(0) > 0
    truthy = {"true", "1", "yes", "y", "t", "1.0", "returned"}
    return s.astype(str).str.strip().str.lower().isin(truthy)


@register(
    key="A21_return_rate",
    analysis_type="operations",
    required_cols=["return_flag", "product_id"],
    optional_cols=["total_amount", "category", "product_name", "order_date"],
    description="Return rate per product and category with monthly trend.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["return_flag", "product_id"])
    df["product_id"] = df["product_id"].astype(str)
    df["_returned"] = _coerce_return_flag(df["return_flag"])

    n_orders = int(len(df))
    if n_orders == 0:
        return _empty("no rows with return_flag + product_id")

    n_returns = int(df["_returned"].sum())
    overall_rate = n_returns / n_orders

    has_revenue = has_col(df, "total_amount")
    if has_revenue:
        df["total_amount"] = coerce_numeric(df["total_amount"]).fillna(0)
        revenue_lost = float(df.loc[df["_returned"], "total_amount"].sum())
    else:
        revenue_lost = None

    # ── Build name map for nicer output ─────────────────────────────────────
    name_map: dict[str, str] = {}
    if has_col(df, "product_name"):
        name_map = (
            df.dropna(subset=["product_name"])
              .drop_duplicates("product_id")
              .set_index("product_id")["product_name"].astype(str).to_dict()
        )

    # ── Per-product aggregation ─────────────────────────────────────────────
    agg_dict = {
        "orders":  ("_returned", "size"),
        "returns": ("_returned", "sum"),
    }
    if has_revenue:
        agg_dict["revenue"]     = ("total_amount", "sum")
        # Revenue lost = sum of total_amount on returned rows.
        df["_returned_revenue"] = df["total_amount"].where(df["_returned"], 0.0)
        agg_dict["revenue_lost"] = ("_returned_revenue", "sum")

    prod = df.groupby("product_id").agg(**agg_dict).reset_index()
    prod["return_rate_pct"] = (prod["returns"] / prod["orders"] * 100).round(2)

    # Eligible for ranking — need a minimum order count so single-return SKUs
    # don't dominate the "highest return rate" leaderboard.
    eligible = prod[prod["orders"] >= MIN_ORDERS_FOR_RANK].copy()
    highest = eligible.nlargest(TOP_N, "return_rate_pct")
    lowest_eligible = eligible[eligible["returns"] > 0].nsmallest(TOP_N, "return_rate_pct")

    by_product = [
        {
            "product_id":      str(r["product_id"]),
            "name":            name_map.get(str(r["product_id"])),
            "orders":          int(r["orders"]),
            "returns":         int(r["returns"]),
            "return_rate_pct": float(r["return_rate_pct"]),
            "revenue":         round(float(r.get("revenue", 0)), 2) if has_revenue else None,
            "revenue_lost":    round(float(r.get("revenue_lost", 0)), 2) if has_revenue else None,
        }
        for r in highest.to_dict("records")
    ]

    # ── Bucket distribution ─────────────────────────────────────────────────
    distribution = []
    for lo, hi, label in RETURN_RATE_BUCKETS:
        n = int(((prod["return_rate_pct"] / 100 >= lo) & (prod["return_rate_pct"] / 100 < hi)).sum())
        distribution.append({
            "bucket":   label,
            "products": n,
            "pct":      round(n / max(len(prod), 1) * 100, 2),
        })

    # ── By category ─────────────────────────────────────────────────────────
    by_category = None
    highest_risk_category = None
    if has_col(df, "category"):
        sub = df.dropna(subset=["category"]).copy()
        sub["category"] = sub["category"].astype(str)
        cat = sub.groupby("category").agg(
            orders=("_returned", "size"),
            returns=("_returned", "sum"),
        ).reset_index()
        cat["return_rate_pct"] = (cat["returns"] / cat["orders"] * 100).round(2)
        cat = cat.sort_values("return_rate_pct", ascending=False)
        by_category = [
            {
                "category":        str(r["category"]),
                "orders":          int(r["orders"]),
                "returns":         int(r["returns"]),
                "return_rate_pct": float(r["return_rate_pct"]),
            }
            for r in cat.to_dict("records")
        ]
        if by_category:
            highest_risk_category = by_category[0]["category"]

    # ── Monthly trend ───────────────────────────────────────────────────────
    monthly_trend = None
    if has_col(df, "order_date"):
        sub = df.copy()
        sub["order_date"] = coerce_date(sub["order_date"])
        sub = sub.dropna(subset=["order_date"])
        if not sub.empty:
            sub["_period"] = sub["order_date"].dt.to_period("M").astype(str)
            tg = sub.groupby("_period").agg(
                orders=("_returned", "size"),
                returns=("_returned", "sum"),
            ).reset_index().sort_values("_period")
            tg["return_rate_pct"] = (tg["returns"] / tg["orders"] * 100).round(2)
            monthly_trend = [
                {
                    "period":          r["_period"],
                    "orders":          int(r["orders"]),
                    "returns":         int(r["returns"]),
                    "return_rate_pct": float(r["return_rate_pct"]),
                }
                for r in tg.to_dict("records")
            ]

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    overall_rate_pct = round(overall_rate * 100, 2)
    headline = build_headline(
        value=overall_rate_pct,
        label=f"return rate · {fmt_int(n_returns)} of {fmt_int(n_orders)} orders",
        trend_pct=None,
        period="All time",
    )

    bullets: list[str] = []
    # 1 — Rate framing + revenue lost
    if overall_rate_pct <= 3:
        bullets.append(
            f"Healthy: {overall_rate_pct:.1f}% return rate "
            f"({fmt_int(n_returns)} of {fmt_int(n_orders)} orders) — "
            f"industry-best territory."
        )
    elif overall_rate_pct <= 10:
        bullets.append(
            f"{overall_rate_pct:.1f}% of orders are returned · "
            + (f"{fmt_money(revenue_lost)} lost." if revenue_lost else "no revenue tag.")
        )
    else:
        bullets.append(
            f"High return rate: {overall_rate_pct:.1f}% "
            + (f"({fmt_money(revenue_lost)} lost) — "
               if revenue_lost else "— ")
            + "investigate top offenders below."
        )

    # 2 — Top offender callout
    if by_product:
        top = by_product[0]
        bullets.append(
            f"Worst SKU: {top['name'] or top['product_id'][:18]} — "
            f"{top['return_rate_pct']:.0f}% return rate ({fmt_int(top['returns'])} of {fmt_int(top['orders'])} orders)."
        )
    elif n_returns > 0:
        bullets.append(
            "Returns are spread across many SKUs — no single product is the culprit, "
            "look at category-level or carrier-level patterns instead."
        )
    else:
        bullets.append(
            "No returns logged in this period — either you're winning, or the "
            "return_flag column isn't populated. Double-check upload tagging."
        )

    # 3 — Category callout or recommendation
    if highest_risk_category and by_category:
        top_cat = by_category[0]
        bullets.append(
            f"{top_cat['category']} is your riskiest category at "
            f"{top_cat['return_rate_pct']:.0f}% returns — audit sizing, quality, or photos."
        )
    elif overall_rate_pct > 10:
        bullets.append(
            "Returns above 10% almost always have a fixable cause: sizing, photo "
            "accuracy, or shipping damage. Pick one and run an experiment this month."
        )
    else:
        bullets.append(
            "Pre-purchase clarity (sizing charts, real photos, honest descriptions) "
            "is the cheapest return-rate intervention you can run."
        )

    actions = [
        action("View return offenders", kind="primary",
               deeplink="/dashboard/products?sort=return-rate-desc", icon="arrow"),
    ]
    if highest_risk_category:
        actions.append(action(
            "Inspect riskiest category", kind="warning",
            deeplink=f"/dashboard/products?category={highest_risk_category}", icon="arrow",
        ))
    actions.append(action(
        "Export returns report", kind="secondary", deeplink=None, icon="download",
    ))

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions[:3],
        ),
        "summary": {
            "n_orders":                n_orders,
            "n_returns":               n_returns,
            "overall_return_rate_pct": overall_rate_pct,
            "n_unique_products":       int(len(prod)),
            "n_products_with_returns": int((prod["returns"] > 0).sum()),
            "revenue_lost_to_returns": round(revenue_lost, 2) if revenue_lost is not None else None,
            "highest_risk_category":   highest_risk_category,
        },
        "highest_return_products": by_product,
        "lowest_eligible_products": [
            {
                "product_id":      str(r["product_id"]),
                "name":            name_map.get(str(r["product_id"])),
                "orders":          int(r["orders"]),
                "returns":         int(r["returns"]),
                "return_rate_pct": float(r["return_rate_pct"]),
            }
            for r in lowest_eligible.to_dict("records")
        ],
        "distribution":  distribution,
        "by_category":   by_category,
        "monthly_trend": monthly_trend,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="return rate", period="no data"),
            fallback_bullets=[
                "No return data yet — this card needs a return_flag + product_id "
                "column on your upload.",
                "Once tagged, this card surfaces your overall return rate, the "
                "worst-offender SKUs, and the riskiest category.",
                "Returns are pure profit leak — even a 2-point drop pays for "
                "most quality-control investments.",
            ],
            suggested_actions=[
                action("Check upload mapping", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {
            "n_orders": 0, "n_returns": 0, "overall_return_rate_pct": 0.0,
            "n_unique_products": 0, "n_products_with_returns": 0,
            "revenue_lost_to_returns": None, "highest_risk_category": None,
        },
        "highest_return_products": [], "lowest_eligible_products": [],
        "distribution": [], "by_category": None, "monthly_trend": None,
        "warning": warning,
    }
