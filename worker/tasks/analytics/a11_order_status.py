"""A11 — Order Status Distribution.

Counts orders by status, normalizes raw status strings into a coarse
success/in_progress/failure category, and reports the operational health
metrics most teams check daily:

    Success rate         = delivered + shipped + completed orders / total
    Cancellation rate    = cancelled / canceled / voided / failed
    Refund rate          = refunded
    In-progress backlog  = pending / processing / invoiced

Status normalization
--------------------
We don't trust the raw `status` field's casing or punctuation — Shopify says
'fulfilled', WooCommerce says 'wc-completed', and analysts copy-paste typos.
We lowercase + strip the value, then keyword-match into:

    SUCCESS    →  delivered, shipped, completed, fulfilled, paid, approved-paid
    PROGRESS   →  pending, processing, invoiced, accepted, ready, packed,
                  in_transit, on_hold, awaiting_*, approved
    FAILURE    →  cancelled, canceled, refunded, voided, failed, rejected,
                  returned, declined, chargeback
    UNKNOWN    →  anything that doesn't match (kept for inspection, not flagged)

The module never *renames* the user's status values — those flow through
verbatim to the UI. The category is an additional metadata column.

Required columns:  status
Optional columns:  total_amount, net_amount, order_id, order_date

Output schema::

    {
      "summary": {
        "n_orders":             int,
        "n_unique_statuses":    int,
        "success_rate_pct":     float,
        "cancellation_rate_pct":float,
        "refund_rate_pct":      float,
        "in_progress_pct":      float,
        "unknown_pct":          float,
        "revenue_at_risk":      float | null   # in_progress + failure revenue
      },
      "by_status": [
        {"status": str, "count": int, "pct": float, "category": str,
         "revenue": float | null, "revenue_pct": float | null}
      ],
      "by_category": [
        {"category": str, "count": int, "pct": float, "revenue": float | null}
      ],
      "monthly_trend": [...] | null,   # if order_date present
      "warning": str | null
    }
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


# Keyword patterns. We match on substring rather than exact equality so
# 'wc-completed', 'COMPLETED ', and 'order_completed' all hit the same bucket.
SUCCESS_KEYWORDS = {"delivered", "shipped", "completed", "complete",
                    "fulfilled", "paid", "received"}
PROGRESS_KEYWORDS = {"pending", "processing", "invoiced", "approved", "accepted",
                     "ready", "packed", "in_transit", "in-transit", "shipping",
                     "on_hold", "on-hold", "awaiting", "open", "new", "placed"}
FAILURE_KEYWORDS = {"cancelled", "canceled", "refunded", "refund", "voided",
                    "void", "failed", "fail", "rejected", "returned", "return",
                    "declined", "chargeback", "disputed", "abandoned"}


def _normalize_status(s: str) -> str:
    """Lower + collapse whitespace + strip. Returns empty string on NaN."""
    if not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("-", "_")
    return s


def _categorize(normalized: str) -> str:
    """Map normalized status → success / in_progress / failure / unknown."""
    if not normalized:
        return "unknown"
    # Failure first (a status like "refund_pending" should be failure not progress).
    if any(k in normalized for k in FAILURE_KEYWORDS):
        return "failure"
    if any(k in normalized for k in SUCCESS_KEYWORDS):
        return "success"
    if any(k in normalized for k in PROGRESS_KEYWORDS):
        return "in_progress"
    return "unknown"


@register(
    key="A11_order_status",
    analysis_type="operations",
    required_cols=["status"],
    optional_cols=["total_amount", "net_amount", "order_id", "order_date"],
    description="Order status distribution + success/cancellation/refund rates.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["status"])
    df["status"] = df["status"].astype(str)
    df["_status_norm"] = df["status"].map(_normalize_status)
    df["_category"] = df["_status_norm"].map(_categorize)

    if df.empty:
        return {
            "summary": {
                "n_orders": 0, "n_unique_statuses": 0,
                "success_rate_pct": 0.0, "cancellation_rate_pct": 0.0,
                "refund_rate_pct": 0.0, "in_progress_pct": 0.0,
                "unknown_pct": 0.0, "revenue_at_risk": None,
            },
            "by_status": [], "by_category": [], "monthly_trend": None,
            "warning": "no rows with a status value after coercion",
        }

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
        df["_revenue"] = df[revenue_col].fillna(0)
        df.loc[df["_revenue"] < 0, "_revenue"] = 0
    n_orders = int(len(df))
    total_rev = float(df["_revenue"].sum()) if has_revenue else 0.0

    # ── Per-status breakdown ────────────────────────────────────────────────
    agg_kwargs = {"count": ("status", "size")}
    if has_revenue:
        agg_kwargs["revenue"] = ("_revenue", "sum")
    by_status_df = (
        df.groupby("status").agg(**agg_kwargs).reset_index()
          .sort_values("count", ascending=False)
    )
    by_status_df["pct"] = (by_status_df["count"] / n_orders * 100).round(2)
    # Re-derive category from the original (raw) status so the user can see
    # which keyword bucket each value mapped to.
    by_status_df["category"] = by_status_df["status"].map(
        lambda s: _categorize(_normalize_status(s))
    )

    by_status: list[dict[str, Any]] = []
    for r in by_status_df.to_dict("records"):
        rec = {
            "status": str(r["status"]),
            "count": int(r["count"]),
            "pct": float(r["pct"]),
            "category": str(r["category"]),
        }
        if has_revenue:
            rev = float(r["revenue"])
            rec["revenue"] = round(rev, 2)
            rec["revenue_pct"] = round(rev / total_rev * 100, 2) if total_rev > 0 else 0.0
        by_status.append(rec)

    # ── Per-category rollup ─────────────────────────────────────────────────
    by_cat_kwargs = {"count": ("status", "size")}
    if has_revenue:
        by_cat_kwargs["revenue"] = ("_revenue", "sum")
    by_cat_df = df.groupby("_category").agg(**by_cat_kwargs).reset_index()
    by_cat_df["pct"] = (by_cat_df["count"] / n_orders * 100).round(2)
    by_category: list[dict[str, Any]] = []
    for r in by_cat_df.to_dict("records"):
        rec = {
            "category": str(r["_category"]),
            "count": int(r["count"]),
            "pct": float(r["pct"]),
        }
        if has_revenue:
            rec["revenue"] = round(float(r["revenue"]), 2)
        by_category.append(rec)

    # ── Headline rates (using normalized buckets) ───────────────────────────
    cat_counts = df["_category"].value_counts()
    success_n = int(cat_counts.get("success", 0))
    progress_n = int(cat_counts.get("in_progress", 0))
    unknown_n = int(cat_counts.get("unknown", 0))

    # Cancellation vs refund are both "failure" but distinct subcategories.
    norm_counts = df["_status_norm"].value_counts()
    cancel_n = int(sum(c for s, c in norm_counts.items()
                       if "cancel" in s or "void" in s or "fail" in s
                       or "reject" in s))
    refund_n = int(sum(c for s, c in norm_counts.items()
                       if "refund" in s or "return" in s or "chargeback" in s))

    # Revenue at risk = anything not yet success.
    revenue_at_risk = None
    if has_revenue:
        revenue_at_risk = round(
            float(df.loc[df["_category"] != "success", "_revenue"].sum()), 2
        )

    # ── Monthly trend (status counts over time) ─────────────────────────────
    monthly_trend = None
    if has_col(df, "order_date"):
        sub = df.copy()
        sub["order_date"] = coerce_date(sub["order_date"])
        sub = sub.dropna(subset=["order_date"])
        if not sub.empty:
            sub["_period"] = sub["order_date"].dt.to_period("M").astype(str)
            piv = (
                sub.groupby(["_period", "_category"]).size().unstack(fill_value=0)
                   .reindex(columns=["success", "in_progress", "failure", "unknown"],
                            fill_value=0)
                   .reset_index()
            )
            piv["total"] = piv[["success", "in_progress", "failure", "unknown"]].sum(axis=1)
            piv["success_rate"] = (piv["success"] / piv["total"] * 100).round(2)
            piv = piv.sort_values("_period")
            monthly_trend = [
                {"period": r["_period"],
                 "success": int(r["success"]),
                 "in_progress": int(r["in_progress"]),
                 "failure": int(r["failure"]),
                 "unknown": int(r["unknown"]),
                 "total": int(r["total"]),
                 "success_rate_pct": float(r["success_rate"])}
                for r in piv.to_dict("records")
            ]

    return {
        "summary": {
            "n_orders": n_orders,
            "n_unique_statuses": int(df["status"].nunique()),
            "success_rate_pct": round(success_n / n_orders * 100, 2),
            "cancellation_rate_pct": round(cancel_n / n_orders * 100, 2),
            "refund_rate_pct": round(refund_n / n_orders * 100, 2),
            "in_progress_pct": round(progress_n / n_orders * 100, 2),
            "unknown_pct": round(unknown_n / n_orders * 100, 2),
            "revenue_at_risk": revenue_at_risk,
        },
        "by_status": by_status,
        "by_category": by_category,
        "monthly_trend": monthly_trend,
        "warning": None,
    }
