"""A14 — Acquisition by Channel.

Splits customers and revenue by `acquisition_channel`, with three rankings
(by revenue, by AOV, by per-customer LTV) so a single number doesn't hide
trade-offs. Also tracks new-customer acquisition over time per channel.

Channel attribution rule
------------------------
Each customer is assigned the `acquisition_channel` value seen on their
*first* order (sorted by `order_date` if available, else first-row order).
This is the standard "first-touch" attribution. Subsequent orders inherit
that channel — even if the row's own value disagrees — so revenue is
attributed to the channel that brought the customer in.

Why per-customer LTV ranking matters
------------------------------------
A channel can win on revenue (just brings volume) but lose on LTV (low-value
customers). Surfacing both means a marketing lead can decide whether to
double down on volume or quality without us hiding the trade-off.

Required columns:  acquisition_channel, customer_id
Optional columns:  order_date, total_amount, net_amount, order_id,
                   customer_segment

Output schema::

    {
      "summary": {
        "n_customers":   int,
        "n_channels":    int,
        "total_revenue": float,
        "best_channel_revenue":  {"name": str, "revenue": float, "share_pct": float},
        "best_channel_aov":      {"name": str, "aov": float},
        "best_channel_ltv":      {"name": str, "avg_ltv": float},
        "channel_concentration": float    # HHI of customer share, 0..1
      },
      "by_channel": [
        {"channel": str, "rank": int, "customers": int, "orders": int,
         "revenue": float, "aov": float, "avg_ltv": float,
         "rev_share_pct": float, "cust_share_pct": float}
      ],
      "monthly_acquisition": [...] | null,    # new customers per channel per month
      "channel_x_segment":   [...] | null,    # if customer_segment present
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


def _herfindahl(shares_pct: pd.Series) -> float:
    """HHI normalized to [0, 1]. Input is percentage shares (0..100)."""
    fractions = shares_pct / 100.0
    return float((fractions ** 2).sum())


@register(
    key="A14_acquisition_channel",
    analysis_type="customer",
    required_cols=["acquisition_channel", "customer_id"],
    optional_cols=["order_date", "total_amount", "net_amount", "order_id",
                   "customer_segment"],
    description="Customer/revenue/AOV/LTV breakdown by acquisition channel.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["acquisition_channel", "customer_id"])
    df["acquisition_channel"] = df["acquisition_channel"].astype(str)
    df["customer_id"] = df["customer_id"].astype(str)

    has_revenue = False
    revenue_col = None
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
        revenue_col = "net_amount"
        has_revenue = True
    elif has_col(df, "total_amount"):
        df["total_amount"] = coerce_numeric(df["total_amount"])
        revenue_col = "total_amount"
        has_revenue = True

    if has_revenue:
        df["_revenue"] = df[revenue_col].fillna(0).clip(lower=0)
    else:
        df["_revenue"] = 0.0

    has_date = has_col(df, "order_date")
    if has_date:
        df["order_date"] = coerce_date(df["order_date"])

    if df.empty:
        return {
            "summary": {
                "n_customers": 0, "n_channels": 0, "total_revenue": 0.0,
                "best_channel_revenue": None, "best_channel_aov": None,
                "best_channel_ltv": None, "channel_concentration": 0.0,
            },
            "by_channel": [], "monthly_acquisition": None,
            "channel_x_segment": None,
            "warning": "no rows with both acquisition_channel and customer_id",
        }

    # ── First-touch attribution ─────────────────────────────────────────────
    # For each customer pick the channel from their first order. If no date
    # is available, take the first row encountered (input order is typically
    # already temporal in raw exports).
    if has_date:
        first_orders = (
            df.dropna(subset=["order_date"])
              .sort_values(["customer_id", "order_date"])
              .drop_duplicates(subset="customer_id", keep="first")
              [["customer_id", "acquisition_channel"]]
        )
    else:
        first_orders = (
            df.drop_duplicates(subset="customer_id", keep="first")
              [["customer_id", "acquisition_channel"]]
        )
    cust_channel = first_orders.set_index("customer_id")["acquisition_channel"]
    df["_first_touch_channel"] = df["customer_id"].map(cust_channel)
    # Customers that somehow lost mapping (NaN order_date everywhere) keep their
    # row-level channel as a fallback.
    df["_first_touch_channel"] = df["_first_touch_channel"].fillna(df["acquisition_channel"])

    n_customers = int(df["customer_id"].nunique())
    total_rev = float(df["_revenue"].sum())

    # ── Per-channel aggregation ─────────────────────────────────────────────
    agg_kwargs = {
        "customers": ("customer_id", "nunique"),
        "revenue": ("_revenue", "sum"),
    }
    if has_col(df, "order_id"):
        df["order_id"] = df["order_id"].astype(str)
        agg_kwargs["orders"] = ("order_id", "nunique")
    else:
        agg_kwargs["orders"] = ("_revenue", "count")

    chan = (
        df.groupby("_first_touch_channel").agg(**agg_kwargs).reset_index()
          .rename(columns={"_first_touch_channel": "channel"})
    )
    chan["aov"] = (chan["revenue"] / chan["orders"]).round(2)
    chan["avg_ltv"] = (chan["revenue"] / chan["customers"]).round(2)
    chan["rev_share_pct"] = (chan["revenue"] / total_rev * 100).round(2) if total_rev > 0 else 0.0
    chan["cust_share_pct"] = (chan["customers"] / n_customers * 100).round(2)
    chan = chan.sort_values("revenue", ascending=False).reset_index(drop=True)
    chan["rank"] = chan.index + 1

    by_channel = [
        {
            "channel": str(r["channel"]),
            "rank": int(r["rank"]),
            "customers": int(r["customers"]),
            "orders": int(r["orders"]),
            "revenue": round(float(r["revenue"]), 2),
            "aov": float(r["aov"]),
            "avg_ltv": float(r["avg_ltv"]),
            "rev_share_pct": float(r["rev_share_pct"]),
            "cust_share_pct": float(r["cust_share_pct"]),
        }
        for r in chan.to_dict("records")
    ]

    # ── Best-channel highlights ─────────────────────────────────────────────
    best_rev = by_channel[0] if by_channel else None
    best_aov_row = max(by_channel, key=lambda r: r["aov"], default=None)
    best_ltv_row = max(by_channel, key=lambda r: r["avg_ltv"], default=None)

    summary = {
        "n_customers": n_customers,
        "n_channels": int(len(by_channel)),
        "total_revenue": round(total_rev, 2),
        "best_channel_revenue": (
            {"name": best_rev["channel"], "revenue": best_rev["revenue"],
             "share_pct": best_rev["rev_share_pct"]} if best_rev else None
        ),
        "best_channel_aov": (
            {"name": best_aov_row["channel"], "aov": best_aov_row["aov"]}
            if best_aov_row else None
        ),
        "best_channel_ltv": (
            {"name": best_ltv_row["channel"], "avg_ltv": best_ltv_row["avg_ltv"]}
            if best_ltv_row else None
        ),
        "channel_concentration": round(
            _herfindahl(chan["cust_share_pct"]), 4
        ),
    }

    # ── New customers per channel per month ─────────────────────────────────
    monthly_acquisition = None
    if has_date:
        first_with_date = (
            df.dropna(subset=["order_date"])
              .sort_values(["customer_id", "order_date"])
              .drop_duplicates(subset="customer_id", keep="first")
        )
        if not first_with_date.empty:
            first_with_date = first_with_date.copy()
            first_with_date["_period"] = first_with_date["order_date"].dt.to_period("M").astype(str)
            counts = (
                first_with_date.groupby(["_period", "acquisition_channel"])
                               .size().reset_index(name="new_customers")
                               .rename(columns={"acquisition_channel": "channel"})
            )
            counts = counts.sort_values(["_period", "channel"])
            monthly_acquisition = [
                {"period": str(r["_period"]), "channel": str(r["channel"]),
                 "new_customers": int(r["new_customers"])}
                for r in counts.to_dict("records")
            ]

    # ── Channel × segment matrix ────────────────────────────────────────────
    channel_x_segment = None
    if has_col(df, "customer_segment"):
        sub = df.dropna(subset=["customer_segment"]).copy()
        if not sub.empty:
            sub["customer_segment"] = sub["customer_segment"].astype(str)
            seg = (
                sub.drop_duplicates(subset=["customer_id"])
                   .groupby(["_first_touch_channel", "customer_segment"])
                   .size().reset_index(name="customers")
                   .rename(columns={"_first_touch_channel": "channel",
                                    "customer_segment": "segment"})
                   .sort_values(["channel", "customers"], ascending=[True, False])
            )
            channel_x_segment = [
                {"channel": str(r["channel"]), "segment": str(r["segment"]),
                 "customers": int(r["customers"])}
                for r in seg.to_dict("records")
            ]

    return {
        "summary": summary,
        "by_channel": by_channel,
        "monthly_acquisition": monthly_acquisition,
        "channel_x_segment": channel_x_segment,
        "warning": None,
    }
