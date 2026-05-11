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

    return {
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
        "summary": {
            "n_customers": 0, "n_orders": 0,
            "one_timer_pct": 0.0, "repeat_customer_pct": 0.0,
        },
        "orders_per_customer_distribution": [],
        "inter_purchase_stats": None,
        "top_customer_timelines": [],
        "warning": warning,
    }
