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

    return {
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
        "summary": {"n_customers": 0, "n_segments": 0, "top_segment": None},
        "segments": [],
        "warning": warning,
    }
