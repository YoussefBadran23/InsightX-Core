"""C04 — New vs Returning Customers.

For each month, splits orders into "from new customers" (first-time buyer
that month) vs "from returning customers" (bought before that month).
Reports monthly trend + overall ratio + revenue contribution per group.

Required columns:  customer_id, order_date
Optional:          total_amount, net_amount, registration_date
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "How many of today's orders came from people who already bought before?"


@register(
    key="C04_new_vs_returning",
    analysis_type="customer",
    required_cols=["customer_id", "order_date"],
    optional_cols=["total_amount", "net_amount", "registration_date"],
    description="Monthly new vs returning customer split with revenue share.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df = df.dropna(subset=["customer_id", "order_date"])
    df["customer_id"] = df["customer_id"].astype(str)

    has_amt = has_col(df, "total_amount") or has_col(df, "net_amount")
    amount_col = None
    if has_amt:
        amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
        df[amount_col] = coerce_numeric(df[amount_col]).fillna(0)

    if df.empty:
        return _empty("no rows after coercion")

    # First order date per customer
    first_orders = df.groupby("customer_id")["order_date"].min()
    df["_first_order"] = df["customer_id"].map(first_orders)
    df["_period"] = df["order_date"].dt.to_period("M")
    df["_first_period"] = df["_first_order"].dt.to_period("M")
    df["_is_new"] = df["_period"] == df["_first_period"]

    n_orders = int(len(df))
    n_customers = int(df["customer_id"].nunique())
    n_new_orders = int(df["_is_new"].sum())
    n_returning_orders = n_orders - n_new_orders

    # Per-month
    grp_cols = {"orders": ("_is_new", "size")}
    if has_amt:
        grp_cols["revenue"] = (amount_col, "sum")

    new_g = df[df["_is_new"]].groupby("_period").agg(**grp_cols).reset_index()
    ret_g = df[~df["_is_new"]].groupby("_period").agg(**grp_cols).reset_index()

    # Build monthly trend
    all_periods = sorted(set(df["_period"].unique()))
    monthly_trend = []
    for p in all_periods:
        new_row = new_g[new_g["_period"] == p]
        ret_row = ret_g[ret_g["_period"] == p]
        new_o = int(new_row["orders"].iloc[0]) if not new_row.empty else 0
        ret_o = int(ret_row["orders"].iloc[0]) if not ret_row.empty else 0
        total = new_o + ret_o
        rec = {
            "period":           str(p),
            "new_orders":       new_o,
            "returning_orders": ret_o,
            "total_orders":     total,
            "new_pct":          round(new_o / total * 100, 2) if total else 0.0,
        }
        if has_amt:
            new_rev = float(new_row["revenue"].iloc[0]) if not new_row.empty else 0.0
            ret_rev = float(ret_row["revenue"].iloc[0]) if not ret_row.empty else 0.0
            rec["new_revenue"]       = round(new_rev, 2)
            rec["returning_revenue"] = round(ret_rev, 2)
        monthly_trend.append(rec)

    summary = {
        "n_orders":                  n_orders,
        "n_customers":               n_customers,
        "n_new_customer_orders":     n_new_orders,
        "n_returning_customer_orders": n_returning_orders,
        "new_orders_pct":            round(n_new_orders / n_orders * 100, 2),
        "returning_orders_pct":      round(n_returning_orders / n_orders * 100, 2),
    }
    if has_amt:
        new_rev_total = float(df.loc[df["_is_new"], amount_col].sum())
        ret_rev_total = float(df.loc[~df["_is_new"], amount_col].sum())
        total_rev = new_rev_total + ret_rev_total
        summary["new_revenue_total"]        = round(new_rev_total, 2)
        summary["returning_revenue_total"]  = round(ret_rev_total, 2)
        summary["returning_revenue_pct"]    = round(ret_rev_total / total_rev * 100, 2) if total_rev else 0.0

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    returning_pct = float(summary.get("returning_orders_pct") or 0)
    headline = build_headline(
        value=round(returning_pct, 1),
        label="orders from returning customers",
        period=f"{fmt_int(n_orders)} total orders",
    )

    bullets: list[str] = []
    if returning_pct >= 50:
        bullets.append(
            f"Healthy: {returning_pct:.1f}% of orders come from returning customers — "
            f"strong loyalty signal, low dependence on constant acquisition."
        )
    elif returning_pct >= 25:
        bullets.append(
            f"OK: {returning_pct:.1f}% returning customers — sustainable but room to "
            f"improve retention via emails and loyalty perks."
        )
    else:
        bullets.append(
            f"Warning: only {returning_pct:.1f}% returning customers — you're refilling "
            f"a leaky bucket. Acquisition spend won't compound without retention."
        )

    if has_amt and summary.get("returning_revenue_pct"):
        rev_pct = float(summary["returning_revenue_pct"])
        bullets.append(
            f"Returning customers contribute {rev_pct:.1f}% of revenue — "
            f"their bigger baskets make them worth keeping."
        )
    else:
        bullets.append(
            f"You added {fmt_int(n_new_orders)} new-customer orders vs "
            f"{fmt_int(n_returning_orders)} returning — track the ratio over time."
        )

    if returning_pct >= 30:
        bullets.append(
            "Launch a VIP tier or referral programme — your repeat customers "
            "are an under-tapped acquisition channel."
        )
    else:
        bullets.append(
            "Wire 30/60/90-day re-engagement emails — bringing back even 10% "
            "of one-time buyers can double LTV."
        )

    actions = [
        action("View at-risk customers", kind="primary",
               deeplink="/dashboard/customers?filter=at-risk", icon="arrow"),
        action("Export new-vs-returning CSV", kind="secondary",
               deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary":       summary,
        "monthly_trend": monthly_trend,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="orders from returning customers", period="no data"),
            fallback_bullets=[
                "No order data yet — needs customer_id + order_date to compute new vs returning.",
                "Once data exists, this card shows the % of orders coming from existing customers each month.",
                "A healthy business should grow this % over time — that's how you stop running on the acquisition treadmill.",
            ],
            suggested_actions=[
                action("Upload data", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {
            "n_orders": 0, "n_customers": 0,
            "n_new_customer_orders": 0, "n_returning_customer_orders": 0,
            "new_orders_pct": 0.0, "returning_orders_pct": 0.0,
        },
        "monthly_trend": [],
        "warning": warning,
    }
