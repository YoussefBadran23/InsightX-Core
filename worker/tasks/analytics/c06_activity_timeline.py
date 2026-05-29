"""C06 — Customer Activity Timeline.

A condensed view of *how customers buy over time*. We don't need to ship a
full per-customer timeline (millions of rows); instead this module surfaces:

- For the top-N customers, their actual order history (date + amount + product/status).
- Aggregate inter-purchase interval stats (mean / median / p90 days between orders).
- Distribution of "orders per customer" buckets.

Required columns:  customer_id, order_date, total_amount
Optional:          product_id, status, net_amount
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "How often do my customers come back to buy again?"


TOP_N_CUSTOMERS = 15
ORDERS_BUCKETS = [
    (1, 2,   "1 order"),
    (2, 3,   "2 orders"),
    (3, 6,   "3-5 orders"),
    (6, 11,  "6-10 orders"),
    (11, 21, "11-20 orders"),
    (21, float("inf"), "20+ orders"),
]


@register(
    key="C06_activity_timeline",
    analysis_type="customer",
    required_cols=["customer_id", "order_date", "total_amount"],
    optional_cols=["product_id", "status", "net_amount"],
    description="Per-customer purchase history with inter-purchase stats.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", "order_date", amount_col])
    df["customer_id"] = df["customer_id"].astype(str)
    df = df[df[amount_col] >= 0]

    if df.empty:
        return _empty("no rows after coercion")

    # Per-customer aggregates.
    g = df.groupby("customer_id").agg(
        n_orders=("order_date", "count"),
        total_spend=(amount_col, "sum"),
        first_order=("order_date", "min"),
        last_order=("order_date", "max"),
    ).reset_index()

    g["lifespan_days"] = (g["last_order"] - g["first_order"]).dt.days
    g["avg_inter_purchase_days"] = np.where(
        g["n_orders"] > 1,
        g["lifespan_days"] / (g["n_orders"] - 1),
        np.nan,
    )

    # Bucket distribution of orders-per-customer.
    distribution = []
    n_total = int(len(g))
    for lo, hi, label in ORDERS_BUCKETS:
        mask = (g["n_orders"] >= lo) & (g["n_orders"] < hi) if hi != float("inf") else g["n_orders"] >= lo
        cnt = int(mask.sum())
        distribution.append({
            "bucket":    label,
            "customers": cnt,
            "pct":       round(cnt / n_total * 100, 2) if n_total else 0.0,
        })

    # Inter-purchase stats (only for repeat buyers)
    repeat = g[g["n_orders"] > 1]
    inter_stats = None
    if not repeat.empty:
        ipd = repeat["avg_inter_purchase_days"].dropna()
        if not ipd.empty:
            inter_stats = {
                "n_repeat_customers": int(len(ipd)),
                "mean_days":   round(float(ipd.mean()), 2),
                "median_days": round(float(ipd.median()), 2),
                "p90_days":    round(float(ipd.quantile(0.90)), 2),
            }

    # Top-N customer timelines.
    top = g.nlargest(TOP_N_CUSTOMERS, "total_spend")["customer_id"].tolist()
    timelines = []
    for cid in top:
        sub = df[df["customer_id"] == cid].sort_values("order_date")
        history = []
        for r in sub.to_dict("records"):
            hist: dict[str, Any] = {
                "date":   str(pd.to_datetime(r["order_date"]).date()),
                "amount": round(float(r[amount_col]), 2),
            }
            if "product_id" in r and pd.notna(r.get("product_id")):
                hist["product_id"] = str(r["product_id"])
            if "status" in r and pd.notna(r.get("status")):
                hist["status"] = str(r["status"])
            history.append(hist)
        timelines.append({
            "customer_id": cid,
            "n_orders":   int(len(history)),
            "total_spend": round(float(sub[amount_col].sum()), 2),
            "history":    history,
        })

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    one_timer_pct = round((g["n_orders"] == 1).mean() * 100, 1)
    repeat_pct = round((g["n_orders"] > 1).mean() * 100, 1)
    headline = build_headline(
        value=repeat_pct,
        label="customers who bought more than once",
        period=f"{fmt_int(n_total)} customers",
    )

    bullets: list[str] = []
    if repeat_pct >= 40:
        bullets.append(
            f"Strong loyalty: {repeat_pct:.1f}% of customers placed multiple orders — "
            f"product-market fit is solid."
        )
    elif repeat_pct >= 20:
        bullets.append(
            f"OK: {repeat_pct:.1f}% repeat-buyer rate. Industry average is 27% — "
            f"room to grow via email + retention campaigns."
        )
    else:
        bullets.append(
            f"Warning: only {repeat_pct:.1f}% repeat buyers ({one_timer_pct:.0f}% are "
            f"one-timers). You're spending heavily to acquire customers who never come back."
        )

    if inter_stats and inter_stats.get("median_days"):
        median = inter_stats["median_days"]
        bullets.append(
            f"Repeat buyers come back every {median:.0f} days on average. "
            f"Trigger your 'we miss you' campaign just before this window."
        )
    else:
        bullets.append(
            f"Most customers ({one_timer_pct:.0f}%) only buy once — automate a "
            f"7-day post-purchase follow-up to convert them into repeat buyers."
        )

    if repeat_pct >= 30:
        bullets.append(
            "Layer a referral programme on top — repeat buyers are 2× more likely "
            "to refer friends than one-time buyers."
        )
    else:
        bullets.append(
            "Set up automated 14/30/60-day re-engagement emails — even moving "
            "repeat rate from 15% to 25% can double customer LTV."
        )

    actions = [
        action("View customer activity", kind="primary",
               deeplink="/dashboard/customers", icon="arrow"),
        action("Export timeline CSV", kind="secondary", deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary": {
            "n_customers":         n_total,
            "n_orders":            int(len(df)),
            "one_timer_pct":       round((g["n_orders"] == 1).mean() * 100, 2),
            "repeat_customer_pct": round((g["n_orders"] > 1).mean() * 100, 2),
        },
        "orders_per_customer_distribution": distribution,
        "inter_purchase_stats":            inter_stats,
        "top_customer_timelines":          timelines,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="customers who bought more than once", period="no data"),
            fallback_bullets=[
                "No customer activity yet — needs customer_id + order_date to compute repeat behaviour.",
                "Once data exists, this card shows the % of repeat buyers and how often they return.",
                "Repeat-buyer rate is the most leveraged growth metric — even small gains compound massively.",
            ],
            suggested_actions=[
                action("Upload data", kind="primary",
                       deeplink="/dashboard/upload", icon="arrow"),
            ],
        ),
        "summary": {
            "n_customers": 0, "n_orders": 0,
            "one_timer_pct": 0.0, "repeat_customer_pct": 0.0,
        },
        "orders_per_customer_distribution": [],
        "inter_purchase_stats": None,
        "top_customer_timelines": [],
        "warning": warning,
    }
