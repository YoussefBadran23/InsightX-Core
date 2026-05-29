"""A10 — Customer Lifetime Stats.

Aggregate per-customer stats: lifetime spend, order count, AOV, lifespan,
and recency. The headline output is the LTV distribution + one-timer vs
repeat split, plus lifespan tiers (new / active / veteran / dormant).

How this differs from A02 RFM and A17 CLV
-----------------------------------------
- A02 RFM: discrete 1–5 quintile scores + segment labels for each customer.
- A10 (this module): continuous lifetime metrics — distributions, percentiles,
  top-spenders. Anchor for dashboards.
- A17 CLV: predicts *future* value via BG/NBD + Gamma-Gamma probabilistic models.

If you're triaging "who are our best customers right now?", reach for A10.
For "who will be best 12 months from now?", reach for A17.

Required columns:  customer_id, total_amount
Optional columns:  net_amount, order_date, order_id

Output schema::

    {
      "summary": {
        "n_customers":           int,
        "total_revenue":         float,
        "avg_lifetime_value":    float,
        "median_lifetime_value": float,
        "p90_lifetime_value":    float,
        "avg_order_count":       float,
        "avg_lifespan_days":     float | null,
        "one_timer_pct":         float,
        "repeat_customer_pct":   float,
        "snapshot_date":         "YYYY-MM-DD" | null
      },
      "spend_distribution": [
        {"bucket": "0-50", "count": int, "pct": float, "revenue_pct": float}
      ],
      "lifespan_distribution": [...] | null,
      "lifespan_tiers": {
        "new":     {"count": int, "criteria": "first order <30d ago"},
        "active":  {...},
        "veteran": {...},
        "dormant": {...}
      } | null,
      "top_spenders": [...],
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int, fmt_money


QUESTION = "What's the average customer worth to me — and who are my whales?"


# Spend buckets in the dataset's currency. We don't try to be cross-currency-
# smart — these are quantile-friendly anchors that read naturally on most
# e-commerce datasets.
SPEND_BUCKETS = [
    (0, 50,    "0-50"),
    (50, 100,  "50-100"),
    (100, 250, "100-250"),
    (250, 500, "250-500"),
    (500, 1000, "500-1k"),
    (1000, 2500, "1k-2.5k"),
    (2500, 5000, "2.5k-5k"),
    (5000, float("inf"), "5k+"),
]

LIFESPAN_BUCKETS = [
    (0, 1,    "single-day"),
    (1, 7,    "1-7 days"),
    (7, 30,   "7-30 days"),
    (30, 90,  "30-90 days"),
    (90, 180, "90-180 days"),
    (180, 365, "180-365 days"),
    (365, float("inf"), "1+ year"),
]


def _bucketize(values: pd.Series, buckets: list[tuple[float, float, str]],
               revenue_for_share: pd.Series | None = None) -> list[dict[str, Any]]:
    """Bin values into named buckets. Optionally include revenue share %."""
    out = []
    n = len(values) or 1
    total_rev = float(revenue_for_share.sum()) if revenue_for_share is not None else 0.0
    for lo, hi, label in buckets:
        mask = (values >= lo) & (values < hi)
        count = int(mask.sum())
        rec = {
            "bucket": label,
            "count": count,
            "pct": round(count / n * 100, 2),
        }
        if revenue_for_share is not None:
            bucket_rev = float(revenue_for_share[mask].sum())
            rec["revenue_pct"] = round(bucket_rev / total_rev * 100, 2) if total_rev > 0 else 0.0
        out.append(rec)
    return out


@register(
    key="A10_customer_lifetime",
    analysis_type="customer",
    required_cols=["customer_id", "total_amount"],
    optional_cols=["net_amount", "order_date", "order_id"],
    description="Per-customer lifetime spend, order count, lifespan, and recency.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])

    revenue_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", revenue_col])
    df = df[df[revenue_col] >= 0]
    df["customer_id"] = df["customer_id"].astype(str)
    df["_revenue"] = df[revenue_col]

    has_date = has_col(df, "order_date")
    if has_date:
        df["order_date"] = coerce_date(df["order_date"])
        df = df.dropna(subset=["order_date"])
        has_date = not df.empty  # may have been emptied by dropna

    if df.empty:
        return {
            **build_payload(
                question=QUESTION,
                headline=build_headline(value=0, label="average lifetime value",
                                        period="no data"),
                fallback_bullets=[
                    "No customer order data yet — lifetime value can't be "
                    "calculated without customer_id + revenue.",
                    "Once data accrues, this card shows your average customer "
                    "spend, your top whales, and the one-timer vs repeat split.",
                    "Knowing LTV unlocks your true acquisition budget: a $50 "
                    "customer can afford a $15 acquisition cost.",
                ],
                suggested_actions=[
                    action("Upload order history", kind="primary",
                           deeplink="/dashboard/upload", icon="arrow"),
                ],
            ),
            "summary": {
                "n_customers": 0, "total_revenue": 0.0,
                "avg_lifetime_value": 0.0, "median_lifetime_value": 0.0,
                "p90_lifetime_value": 0.0, "avg_order_count": 0.0,
                "avg_lifespan_days": None, "one_timer_pct": 0.0,
                "repeat_customer_pct": 0.0, "snapshot_date": None,
            },
            "spend_distribution": [], "lifespan_distribution": None,
            "lifespan_tiers": None, "top_spenders": [],
            "warning": "no rows with both customer_id and revenue after coercion",
        }

    # ── Per-customer aggregation ────────────────────────────────────────────
    agg_kwargs = {
        "lifetime_value": ("_revenue", "sum"),
        "order_count": ("_revenue", "count"),
    }
    if has_col(df, "order_id"):
        df["order_id"] = df["order_id"].astype(str)
        agg_kwargs["order_count"] = ("order_id", "nunique")
    if has_date:
        agg_kwargs["first_order"] = ("order_date", "min")
        agg_kwargs["last_order"] = ("order_date", "max")

    cust = df.groupby("customer_id").agg(**agg_kwargs).reset_index()
    cust["aov"] = (cust["lifetime_value"] / cust["order_count"]).round(2)

    snapshot = None
    if has_date:
        snapshot = df["order_date"].max()
        cust["lifespan_days"] = (cust["last_order"] - cust["first_order"]).dt.days
        cust["recency_days"] = (snapshot - cust["last_order"]).dt.days
        cust["first_order"] = cust["first_order"].dt.date
        cust["last_order"] = cust["last_order"].dt.date

    n_customers = int(len(cust))
    total_rev = float(cust["lifetime_value"].sum())
    one_timers = int((cust["order_count"] == 1).sum())
    repeat = n_customers - one_timers

    avg_ltv = float(cust["lifetime_value"].mean())
    med_ltv = float(cust["lifetime_value"].median())
    p90_ltv = float(cust["lifetime_value"].quantile(0.90))
    avg_orders = float(cust["order_count"].mean())
    avg_lifespan = float(cust["lifespan_days"].mean()) if has_date else None

    # ── Spend distribution buckets ──────────────────────────────────────────
    spend_dist = _bucketize(cust["lifetime_value"], SPEND_BUCKETS,
                             revenue_for_share=cust["lifetime_value"])

    # ── Lifespan distribution + tiers ───────────────────────────────────────
    lifespan_dist = None
    lifespan_tiers = None
    if has_date:
        lifespan_dist = _bucketize(cust["lifespan_days"].astype(float), LIFESPAN_BUCKETS)

        # Tier rules (industry-typical thresholds):
        # - new:     first_order < 30 days ago AND order_count == 1
        # - active:  recency_days <= 90 AND order_count >= 2
        # - dormant: recency_days > 90 (regardless of order_count)
        # - veteran: lifespan_days >= 365 AND recency_days <= 90
        # Order matters: dormant trumps veteran/active because we report
        # "current state" not "historical category".
        days_since_first = (snapshot - pd.to_datetime(cust["first_order"])).dt.days

        is_dormant = cust["recency_days"] > 90
        is_new = (days_since_first < 30) & (cust["order_count"] == 1) & (~is_dormant)
        is_veteran = (cust["lifespan_days"] >= 365) & (cust["recency_days"] <= 90)
        is_active = (cust["order_count"] >= 2) & (cust["recency_days"] <= 90) & (~is_veteran)

        # Anyone unaccounted for → also "active" by elimination.
        accounted = is_dormant | is_new | is_veteran | is_active
        is_active = is_active | (~accounted & ~is_dormant)

        lifespan_tiers = {
            "new":     {"count": int(is_new.sum()),
                        "criteria": "first order <30 days ago, single order"},
            "active":  {"count": int(is_active.sum()),
                        "criteria": "≥2 orders, last order within 90 days"},
            "veteran": {"count": int(is_veteran.sum()),
                        "criteria": "≥1 year lifespan, active in last 90 days"},
            "dormant": {"count": int(is_dormant.sum()),
                        "criteria": "no order in last 90 days"},
        }

    # ── Top spenders ────────────────────────────────────────────────────────
    top = cust.nlargest(20, "lifetime_value")
    top_spenders = []
    for r in top.to_dict("records"):
        rec = {
            "customer_id": str(r["customer_id"]),
            "lifetime_value": round(float(r["lifetime_value"]), 2),
            "order_count": int(r["order_count"]),
            "aov": round(float(r["aov"]), 2),
        }
        if has_date and r.get("first_order") is not None:
            rec["first_order"] = str(r["first_order"])
            rec["last_order"] = str(r["last_order"])
            rec["lifespan_days"] = int(r.get("lifespan_days", 0))
            rec["recency_days"] = int(r.get("recency_days", 0))
        top_spenders.append(rec)

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    one_timer_pct = round(one_timers / n_customers * 100, 2)
    repeat_pct = round(repeat / n_customers * 100, 2)

    headline = build_headline(
        value=round(avg_ltv, 2),
        label="average lifetime value per customer",
        period=f"{fmt_int(n_customers)} customers",
    )

    bullets: list[str] = []
    # 1 — Whale callout (p90 vs median tells you skew)
    if med_ltv > 0 and p90_ltv >= med_ltv * 2:
        bullets.append(
            f"Top 10% spend {fmt_money(p90_ltv)}+ — that's {p90_ltv / med_ltv:.1f}× the median "
            f"({fmt_money(med_ltv)}). Whale-heavy revenue."
        )
    else:
        bullets.append(
            f"Median lifetime spend: {fmt_money(med_ltv)} · top 10% reach {fmt_money(p90_ltv)} "
            f"— revenue is evenly distributed across customers."
        )

    # 2 — Repeat-rate framing
    if repeat_pct >= 50:
        bullets.append(
            f"Strong: {repeat_pct:.0f}% of customers come back — your retention loop is working."
        )
    elif repeat_pct >= 25:
        bullets.append(
            f"{repeat_pct:.0f}% repeat-customer rate is decent — push post-purchase emails "
            f"to convert more one-timers."
        )
    else:
        bullets.append(
            f"Only {repeat_pct:.0f}% buy again ({one_timer_pct:.0f}% are one-timers) — "
            f"there's huge upside in turning these into repeats."
        )

    # 3 — Lifespan-tier action prompt
    if lifespan_tiers:
        dormant_n = int(lifespan_tiers["dormant"]["count"])
        veteran_n = int(lifespan_tiers["veteran"]["count"])
        if dormant_n > 0:
            bullets.append(
                f"{fmt_int(dormant_n)} customers haven't ordered in 90+ days — "
                f"a win-back email today is cheaper than acquiring a new one."
            )
        elif veteran_n > 0:
            bullets.append(
                f"{fmt_int(veteran_n)} veteran customers (1+ year, still buying) — "
                f"send them a loyalty perk; they're your evangelists."
            )
        else:
            bullets.append(
                "Customer base is young — focus on 30/60/90-day onboarding emails "
                "to convert first orders into repeats."
            )
    else:
        bullets.append(
            "Add order_date to your upload to unlock lifespan tiers and dormant-customer alerts."
        )

    actions = [
        action("View top spenders", kind="primary",
               deeplink="/dashboard/customers?sort=ltv-desc", icon="arrow"),
    ]
    if lifespan_tiers and int(lifespan_tiers["dormant"]["count"]) > 0:
        actions.append(action(
            "Win back dormant", kind="warning",
            deeplink="/dashboard/segmentation?segment=dormant", icon="arrow",
        ))
    actions.append(action(
        "Export LTV report", kind="secondary", deeplink=None, icon="download",
    ))

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions[:3],
        ),
        "summary": {
            "n_customers": n_customers,
            "total_revenue": round(total_rev, 2),
            "avg_lifetime_value": round(avg_ltv, 2),
            "median_lifetime_value": round(med_ltv, 2),
            "p90_lifetime_value": round(p90_ltv, 2),
            "avg_order_count": round(avg_orders, 3),
            "avg_lifespan_days": round(avg_lifespan, 2) if avg_lifespan is not None else None,
            "one_timer_pct": one_timer_pct,
            "repeat_customer_pct": repeat_pct,
            "snapshot_date": snapshot.date().isoformat() if snapshot is not None else None,
        },
        "spend_distribution": spend_dist,
        "lifespan_distribution": lifespan_dist,
        "lifespan_tiers": lifespan_tiers,
        "top_spenders": top_spenders,
        "warning": None,
    }
