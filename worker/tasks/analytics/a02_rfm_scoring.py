"""A02 — RFM Scoring & Segmentation.

Classic RFM (Recency, Frequency, Monetary) scoring per customer, plus a
business-friendly segment label per customer. The snapshot date is the most
recent `order_date` in the dataset (a deterministic anchor — no `datetime.now()`
so re-runs on the same CSV produce identical results).

Score components
----------------
- **Recency**: days between snapshot date and the customer's last order.
  Lower is better → reverse the quintile so 5 = most recent.
- **Frequency**: number of orders. Higher is better → 5 = most frequent.
  We rank with `method='first'` to avoid `qcut` blowing up when many
  customers share the same order count (very common: lots of one-time buyers).
- **Monetary**: total spend (uses `net_amount` if present, else `total_amount`).
  Higher is better → 5 = highest spenders.

Combined `RFM_score` is the concatenated string "RFM" (e.g., "555" = best).

Segment labels (industry-standard taxonomy)
-------------------------------------------
- Champions:           R 4-5, F 4-5, M 4-5  — recent, frequent, high-spend
- Loyal Customers:     F 3-5, R 3-5         — repeat buyers, still active
- Potential Loyalists: R 4-5, F 1-3         — new but engaged
- New Customers:       R 4-5, F 1           — recent first purchase
- Promising:           R 3-4, F 1-2, M 1-3  — recent low-value
- Need Attention:      R 3, F 3, M 3        — middle of the road
- About to Sleep:      R 2-3, F 1-3
- At Risk:             R 1-2, F 2-5, M 2-5  — used to spend, drifted
- Cannot Lose Them:    R 1-2, F 4-5, M 4-5  — high-value, gone quiet
- Hibernating:         R 1-2, F 1-2, M 1-2
- Lost:                R 1, F 1, M 1        — long-gone, low-value

Required columns:  customer_id, order_date, total_amount
Optional columns:  net_amount

Output schema::

    {
      "summary": {
        "n_customers":    int,
        "snapshot_date":  "YYYY-MM-DD",
        "total_revenue":  float,
        "avg_recency":    float,   # days
        "avg_frequency":  float,
        "avg_monetary":   float
      },
      "segments": [
        {"segment": "Champions", "count": int, "pct": float,
         "revenue": float, "rev_pct": float, "avg_monetary": float}
      ],
      "score_distribution": {
        "R": {"1": int, "2": int, ..., "5": int},
        "F": {...},
        "M": {...}
      },
      "top_customers": [
        {"customer_id": str, "recency_days": int, "frequency": int,
         "monetary": float, "R": int, "F": int, "M": int,
         "RFM_score": "555", "segment": "Champions"}
      ]
    }
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


def _safe_quintile(s: pd.Series, ascending: bool = True) -> pd.Series:
    """Rank a series into 5 buckets robustly.

    `pd.qcut(..., q=5)` raises when there aren't enough unique values to form
    5 distinct edges — common for `frequency` (many customers with 1 order).
    We rank first (method='first' breaks ties stably), then `qcut` on the rank.
    """
    ranks = s.rank(method="first", ascending=ascending)
    try:
        bins = pd.qcut(ranks, q=5, labels=[1, 2, 3, 4, 5])
    except ValueError:
        # Fallback: too few unique values — bucket linearly across [1,5].
        bins = pd.cut(ranks, bins=5, labels=[1, 2, 3, 4, 5], include_lowest=True)
    return bins.astype(int)


def _segment_label(r: int, f: int, m: int) -> str:
    """Map (R, F, M) scores to a human-readable segment.

    Order matters: more specific rules first. Each customer falls into exactly
    one bucket — the first matching condition wins.
    """
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r <= 2 and f >= 4 and m >= 4:
        return "Cannot Lose Them"
    if r >= 3 and f >= 3:
        return "Loyal Customers"
    if r >= 4 and f == 1:
        return "New Customers"
    if r >= 4 and f <= 3:
        return "Potential Loyalists"
    if r == 3 and f == 3 and m == 3:
        return "Need Attention"
    if r <= 2 and f >= 2 and m >= 2:
        return "At Risk"
    if r >= 3 and f <= 2 and m <= 3:
        return "Promising"
    if 2 <= r <= 3 and f <= 3:
        return "About to Sleep"
    if r <= 2 and f <= 2 and m <= 2:
        return "Hibernating"
    if r == 1 and f == 1 and m == 1:
        return "Lost"
    return "Other"


@register(
    key="A02_rfm_scoring",
    analysis_type="customer",
    required_cols=["customer_id", "order_date", "total_amount"],
    optional_cols=["net_amount"],
    description="RFM scoring + segmentation (Champions / Loyal / At Risk / Lost / ...).",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])

    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", "order_date", amount_col])
    df = df[df[amount_col] >= 0]
    df["customer_id"] = df["customer_id"].astype(str)

    if df.empty or df["customer_id"].nunique() < 5:
        # Need at least 5 customers to form quintiles meaningfully.
        return {
            "summary": {
                "n_customers": int(df["customer_id"].nunique()) if not df.empty else 0,
                "snapshot_date": None, "total_revenue": 0.0,
                "avg_recency": 0.0, "avg_frequency": 0.0, "avg_monetary": 0.0,
            },
            "segments": [], "score_distribution": {"R": {}, "F": {}, "M": {}},
            "top_customers": [],
            "warning": "insufficient_data — need >=5 distinct customers for RFM quintiles",
        }

    snapshot = df["order_date"].max()

    # ── Per-customer RFM table ──────────────────────────────────────────────
    rfm = df.groupby("customer_id").agg(
        recency_days=("order_date", lambda s: int((snapshot - s.max()).days)),
        frequency=("order_date", "count"),
        monetary=(amount_col, "sum"),
    ).reset_index()

    # Score: R inverted (lower recency = higher score), F & M ascending.
    rfm["R"] = _safe_quintile(rfm["recency_days"], ascending=False)
    rfm["F"] = _safe_quintile(rfm["frequency"], ascending=True)
    rfm["M"] = _safe_quintile(rfm["monetary"], ascending=True)
    rfm["RFM_score"] = rfm["R"].astype(str) + rfm["F"].astype(str) + rfm["M"].astype(str)
    rfm["segment"] = [_segment_label(r, f, m) for r, f, m in zip(rfm["R"], rfm["F"], rfm["M"])]

    total_rev = float(rfm["monetary"].sum())

    # ── Segment summary ─────────────────────────────────────────────────────
    seg_summary = (
        rfm.groupby("segment").agg(
            count=("customer_id", "count"),
            revenue=("monetary", "sum"),
            avg_monetary=("monetary", "mean"),
        ).reset_index().sort_values("revenue", ascending=False)
    )
    seg_summary["pct"] = (seg_summary["count"] / len(rfm) * 100).round(2)
    seg_summary["rev_pct"] = (seg_summary["revenue"] / total_rev * 100).round(2) if total_rev > 0 else 0.0

    score_dist = {
        "R": rfm["R"].value_counts().sort_index().to_dict(),
        "F": rfm["F"].value_counts().sort_index().to_dict(),
        "M": rfm["M"].value_counts().sort_index().to_dict(),
    }
    # Cast keys to str so JSON keys are stable.
    score_dist = {k: {str(int(kk)): int(vv) for kk, vv in v.items()} for k, v in score_dist.items()}

    top = rfm.nlargest(20, "monetary")

    return {
        "summary": {
            "n_customers": int(len(rfm)),
            "snapshot_date": snapshot.date().isoformat(),
            "total_revenue": round(total_rev, 2),
            "avg_recency": round(float(rfm["recency_days"].mean()), 2),
            "avg_frequency": round(float(rfm["frequency"].mean()), 2),
            "avg_monetary": round(float(rfm["monetary"].mean()), 2),
        },
        "segments": [
            {
                "segment": r["segment"],
                "count": int(r["count"]),
                "pct": float(r["pct"]),
                "revenue": round(float(r["revenue"]), 2),
                "rev_pct": float(r["rev_pct"]),
                "avg_monetary": round(float(r["avg_monetary"]), 2),
            }
            for r in seg_summary.to_dict("records")
        ],
        "score_distribution": score_dist,
        "top_customers": [
            {
                "customer_id": str(r["customer_id"]),
                "recency_days": int(r["recency_days"]),
                "frequency": int(r["frequency"]),
                "monetary": round(float(r["monetary"]), 2),
                "R": int(r["R"]), "F": int(r["F"]), "M": int(r["M"]),
                "RFM_score": str(r["RFM_score"]),
                "segment": str(r["segment"]),
            }
            for r in top.to_dict("records")
        ],
    }
