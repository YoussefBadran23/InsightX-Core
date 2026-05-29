"""A22 — Fulfillment SLA Analysis.

Distribution of `delivery_days` plus SLA-compliance rate. Default SLA is 7
days; the dashboard can pass a custom threshold via env or future param.

Required columns:  delivery_days
Optional columns:  status, order_date, region, country, product_id, category
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "Are my orders shipping and arriving on time?"

SLA_THRESHOLD_DAYS = 7
DELIVERY_BUCKETS = [
    (-float("inf"), 0,    "same/next-day"),
    (0,             3,    "0-2 days"),
    (3,             7,    "3-6 days"),
    (7,             14,   "1-2 weeks"),
    (14,            30,   "2-4 weeks"),
    (30,            float("inf"), "1 month+"),
]


@register(
    key="A22_fulfillment_sla",
    analysis_type="operations",
    required_cols=["delivery_days"],
    optional_cols=["status", "order_date", "region", "country", "product_id", "category"],
    description="Delivery time distribution + SLA-compliance rate.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["delivery_days"] = coerce_numeric(df["delivery_days"])
    df = df.dropna(subset=["delivery_days"])
    df = df[df["delivery_days"] >= 0]

    n_orders = int(len(df))
    if n_orders == 0:
        return _empty("no rows with delivery_days >= 0")

    dd = df["delivery_days"].astype(float)
    avg     = float(dd.mean())
    median  = float(dd.median())
    p90     = float(dd.quantile(0.90))
    p99     = float(dd.quantile(0.99))
    n_within = int((dd <= SLA_THRESHOLD_DAYS).sum())

    # ── Distribution buckets ────────────────────────────────────────────────
    distribution = []
    for lo, hi, label in DELIVERY_BUCKETS:
        mask = (dd >= lo) & (dd < hi) if hi != float("inf") else dd >= lo
        n = int(mask.sum())
        distribution.append({
            "bucket": label,
            "orders": n,
            "pct":    round(n / n_orders * 100, 2),
        })

    # ── By region (if available) ────────────────────────────────────────────
    by_region = None
    if has_col(df, "region"):
        sub = df.dropna(subset=["region"]).copy()
        sub["region"] = sub["region"].astype(str)
        rg = sub.groupby("region").agg(
            orders=("delivery_days", "size"),
            avg_delivery_days=("delivery_days", "mean"),
            median_delivery_days=("delivery_days", "median"),
            within_sla=("delivery_days", lambda s: int((s <= SLA_THRESHOLD_DAYS).sum())),
        ).reset_index()
        rg["sla_compliance_pct"] = (rg["within_sla"] / rg["orders"] * 100).round(2)
        rg = rg.sort_values("avg_delivery_days")
        by_region = [
            {
                "region":               str(r["region"]),
                "orders":               int(r["orders"]),
                "avg_delivery_days":    round(float(r["avg_delivery_days"]), 2),
                "median_delivery_days": round(float(r["median_delivery_days"]), 2),
                "sla_compliance_pct":   float(r["sla_compliance_pct"]),
            }
            for r in rg.to_dict("records")
        ]

    # ── By status ───────────────────────────────────────────────────────────
    by_status = None
    if has_col(df, "status"):
        sub = df.dropna(subset=["status"]).copy()
        sub["status"] = sub["status"].astype(str)
        st = sub.groupby("status").agg(
            orders=("delivery_days", "size"),
            avg_delivery_days=("delivery_days", "mean"),
        ).reset_index()
        st = st.sort_values("orders", ascending=False)
        by_status = [
            {
                "status":            str(r["status"]),
                "orders":            int(r["orders"]),
                "avg_delivery_days": round(float(r["avg_delivery_days"]), 2),
            }
            for r in st.to_dict("records")
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
                orders=("delivery_days", "size"),
                avg_delivery_days=("delivery_days", "mean"),
                within_sla=("delivery_days", lambda s: int((s <= SLA_THRESHOLD_DAYS).sum())),
            ).reset_index().sort_values("_period")
            tg["sla_compliance_pct"] = (tg["within_sla"] / tg["orders"] * 100).round(2)
            monthly_trend = [
                {
                    "period":            r["_period"],
                    "orders":            int(r["orders"]),
                    "avg_delivery_days": round(float(r["avg_delivery_days"]), 2),
                    "sla_compliance_pct": float(r["sla_compliance_pct"]),
                }
                for r in tg.to_dict("records")
            ]

    # ── Worst-delivery outliers ─────────────────────────────────────────────
    worst = df.nlargest(min(15, n_orders), "delivery_days")
    worst_orders = []
    for r in worst.to_dict("records"):
        rec: dict[str, Any] = {"delivery_days": int(r["delivery_days"])}
        if "order_date" in r and pd.notna(r.get("order_date")):
            rec["order_date"] = str(pd.to_datetime(r["order_date"]).date())
        for c in ("region", "country", "product_id", "status"):
            if c in r and pd.notna(r.get(c)):
                rec[c] = str(r[c])
        worst_orders.append(rec)

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    compliance_pct = round(n_within / n_orders * 100, 2)
    n_late = n_orders - n_within
    headline = build_headline(
        value=compliance_pct,
        label=f"on-time delivery (≤{SLA_THRESHOLD_DAYS}d SLA)",
        trend_pct=None,
        period=f"{fmt_int(n_orders)} orders measured",
    )

    bullets: list[str] = []
    # 1 — SLA framing
    if compliance_pct >= 90:
        bullets.append(
            f"Strong: {compliance_pct:.1f}% of orders arrive within the {SLA_THRESHOLD_DAYS}-day SLA — "
            f"keep your carrier mix; it's working."
        )
    elif compliance_pct >= 75:
        bullets.append(
            f"OK: {compliance_pct:.1f}% on-time, but {fmt_int(n_late)} orders missed SLA — "
            f"investigate which regions or carriers slipped."
        )
    else:
        bullets.append(
            f"Warning: only {compliance_pct:.1f}% on-time. {fmt_int(n_late)} late deliveries "
            f"drive refund risk and bad reviews — escalate to carrier."
        )

    # 2 — Distribution detail
    bullets.append(
        f"Average delivery: {avg:.1f} days · median {median:.1f} · "
        f"90th percentile {p90:.1f} — half your customers wait under {median:.0f} days."
    )

    # 3 — Worst-region or worst-status callout
    worst_region = None
    if by_region:
        slowest = min(by_region, key=lambda r: r.get("sla_compliance_pct", 100))
        if slowest.get("sla_compliance_pct", 100) < compliance_pct - 5:
            worst_region = slowest

    if worst_region:
        bullets.append(
            f"Worst region: {worst_region['region']} at "
            f"{worst_region['sla_compliance_pct']:.0f}% on-time "
            f"({worst_region['avg_delivery_days']:.1f}d avg) — review carrier coverage there."
        )
    elif compliance_pct < 85:
        bullets.append(
            "Switch your slowest carrier for any orders going to your top-3 "
            "delayed regions — even a 1-day improvement compounds fast."
        )
    else:
        bullets.append(
            "Promise 1 day SHORTER than your true delivery — under-promise + "
            "over-deliver beats the inverse every time."
        )

    actions = [
        action("Drill into late orders", kind="primary",
               deeplink=f"/dashboard/analytics?focus=A22&filter=late",
               icon="arrow"),
    ]
    if compliance_pct < 80:
        actions.append(action(
            "Compare carrier performance", kind="warning",
            deeplink="/dashboard/analytics?focus=A22&group=carrier",
            icon="arrow",
        ))
    actions.append(action(
        "Export SLA report", kind="secondary", deeplink=None, icon="download",
    ))

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions[:3],
        ),
        "summary": {
            "n_orders":             n_orders,
            "sla_threshold_days":   SLA_THRESHOLD_DAYS,
            "sla_compliance_pct":   round(n_within / n_orders * 100, 2),
            "avg_delivery_days":    round(avg, 2),
            "median_delivery_days": round(median, 2),
            "p90_delivery_days":    round(p90, 2),
            "p99_delivery_days":    round(p99, 2),
            "max_delivery_days":    int(dd.max()),
        },
        "distribution":  distribution,
        "by_region":     by_region,
        "by_status":     by_status,
        "monthly_trend": monthly_trend,
        "worst_orders":  worst_orders,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="on-time delivery (no data)",
                                    period="no data"),
            fallback_bullets=[
                "No `delivery_days` column found — fulfillment SLA can't be "
                "measured without it.",
                "Compute it as: order_delivered_date - order_purchase_date "
                "before upload, or have your store export it.",
                "Once tagged, this card surfaces on-time rate, slowest region, "
                "and worst-15 delivery outliers.",
            ],
            suggested_actions=[
                action("Add delivery dates", kind="primary",
                       deeplink="/dashboard/settings/data-sources", icon="arrow"),
            ],
        ),
        "summary": {
            "n_orders": 0, "sla_threshold_days": SLA_THRESHOLD_DAYS,
            "sla_compliance_pct": 0.0, "avg_delivery_days": 0.0,
            "median_delivery_days": 0.0, "p90_delivery_days": 0.0,
            "p99_delivery_days": 0.0, "max_delivery_days": 0,
        },
        "distribution": [], "by_region": None, "by_status": None,
        "monthly_trend": None, "worst_orders": [],
        "warning": warning,
    }
