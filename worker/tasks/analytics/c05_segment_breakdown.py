"""C05 — Customer Segment Breakdown.

Pie-chart-friendly distribution of customers across the `customer_segment`
column (if the source data tagged its own segments — VIP/Standard/etc.).
Unlike A02 (computed RFM) and A19 (K-Means), this reflects the customer's
PRE-TAGGED segment as it appeared on the CSV.

Required columns:  customer_id, customer_segment
Optional:          total_amount, net_amount
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._base import coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int, fmt_money


QUESTION = "What's the mix of my customer segments?"


@register(
    key="C05_segment_breakdown",
    analysis_type="customer",
    required_cols=["customer_id", "customer_segment"],
    optional_cols=["total_amount", "net_amount"],
    description="Distribution of customers by source-tagged customer_segment.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["customer_id", "customer_segment"])
    df["customer_id"]      = df["customer_id"].astype(str)
    df["customer_segment"] = df["customer_segment"].astype(str).str.strip()
    df = df[df["customer_segment"] != ""]

    if df.empty:
        return _empty("no rows with non-empty customer_segment")

    has_amt = has_col(df, "total_amount") or has_col(df, "net_amount")
    amount_col = None
    if has_amt:
        amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
        df[amount_col] = coerce_numeric(df[amount_col]).fillna(0)

    # Dedupe to one row per customer.
    cust = df.drop_duplicates("customer_id", keep="last")
    n_customers = int(len(cust))

    agg_kwargs = {"customers": ("customer_id", "nunique")}
    if has_amt:
        agg_kwargs["revenue"] = (amount_col, "sum")
    g = df.groupby("customer_segment").agg(**agg_kwargs).reset_index()
    g = g.sort_values("customers", ascending=False)
    total_rev = float(g["revenue"].sum()) if has_amt else 0.0

    segments = []
    for r in g.to_dict("records"):
        rec: dict[str, Any] = {
            "segment":   str(r["customer_segment"]),
            "customers": int(r["customers"]),
            "pct":       round(int(r["customers"]) / n_customers * 100, 2),
        }
        if has_amt:
            rec["revenue"]     = round(float(r["revenue"]), 2)
            rec["rev_pct"]     = round(float(r["revenue"]) / total_rev * 100, 2) if total_rev else 0.0
            rec["avg_revenue_per_customer"] = round(float(r["revenue"]) / int(r["customers"]), 2)
        segments.append(rec)

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    top_seg = segments[0] if segments else None
    n_segments = int(len(segments))
    headline = build_headline(
        value=n_segments,
        label="customer segments identified",
        period=f"{fmt_int(n_customers)} customers",
    )

    bullets: list[str] = []
    if top_seg:
        bullets.append(
            f"Largest segment: {top_seg['segment']} — {fmt_int(top_seg['customers'])} "
            f"customers ({top_seg['pct']:.0f}% of base)."
        )
    else:
        bullets.append(f"Tracking {fmt_int(n_customers)} customers but no segments yet.")

    if has_amt and top_seg and top_seg.get("rev_pct"):
        bullets.append(
            f"Top segment also drives {top_seg['rev_pct']:.0f}% of revenue — "
            f"protect this group with personalised retention."
        )
    elif n_segments >= 5:
        bullets.append(
            f"You have {n_segments} distinct segments — broad enough to test "
            f"per-segment marketing campaigns."
        )
    else:
        bullets.append(
            f"Only {n_segments} segments — consider deeper segmentation (RFM, "
            f"behaviour, value tier) for sharper targeting."
        )

    if n_segments >= 4 and top_seg and top_seg.get("pct", 0) >= 50:
        bullets.append(
            f"{top_seg['pct']:.0f}% of customers cluster in one segment — high "
            f"concentration. Look for sub-segments within it for finer targeting."
        )
    else:
        bullets.append(
            "Run a per-segment promo: same offer, different creative tailored "
            "to each segment. Compare conversion rates to find the winning angle."
        )

    actions = [
        action("View segmentation", kind="primary",
               deeplink="/dashboard/segmentation", icon="arrow"),
        action("Export segments CSV", kind="secondary", deeplink=None, icon="download"),
    ]

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions,
        ),
        "summary": {
            "n_customers":  n_customers,
            "n_segments":   int(len(segments)),
            "top_segment":  segments[0] if segments else None,
        },
        "segments": segments,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="customer segments identified", period="no data"),
            fallback_bullets=[
                "No segment data yet — add a customer_segment column or run A02 RFM Scoring to populate this.",
                "Without segmentation, every customer is treated the same — losing the highest-ROI marketing lever.",
                "RFM segments (Champions, Loyal, At-Risk, Lost) are a great first cut; refine over time.",
            ],
            suggested_actions=[
                action("Run RFM scoring", kind="primary",
                       deeplink="/dashboard/analytics?focus=A02", icon="arrow"),
            ],
        ),
        "summary": {"n_customers": 0, "n_segments": 0, "top_segment": None},
        "segments": [],
        "warning": warning,
    }
