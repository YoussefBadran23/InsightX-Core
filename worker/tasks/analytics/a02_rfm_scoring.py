"""A02 — RFM Scoring.

Recency-Frequency-Monetary analysis per customer.
Assigns R/F/M quintile scores (1-5) and named segments.
Updates customers.rfm_score and customers.rfm_segment.
"""

import pandas as pd
from sqlalchemy import text
from ._base import analytics_task, has_col


# ── Segment mapping ────────────────────────────────────────────────────────

_RFM_SEGMENTS = {
    # (R_min, R_max, F_min, F_max, M_min, M_max) → segment_name
    "Champions":        lambda r, f, m: r >= 4 and f >= 4 and m >= 4,
    "Loyal":            lambda r, f, m: f >= 3 and m >= 3,
    "Potential Loyalist": lambda r, f, m: r >= 3 and f >= 2 and m >= 2,
    "Recent Customers": lambda r, f, m: r >= 4 and f <= 2,
    "Promising":        lambda r, f, m: r >= 3 and f <= 2,
    "Needs Attention":  lambda r, f, m: r == 3 and f == 3,
    "About to Sleep":   lambda r, f, m: r == 2 and f >= 2,
    "At Risk":          lambda r, f, m: r <= 2 and f >= 3,
    "Hibernating":      lambda r, f, m: r <= 2 and f <= 2 and m <= 2,
    "Lost":             lambda r, f, m: r == 1 and f == 1,
}


def _assign_segment(r: int, f: int, m: int) -> str:
    for name, rule in _RFM_SEGMENTS.items():
        if rule(r, f, m):
            return name
    return "Other"


@analytics_task("A02_rfm_scoring", "rfm")
def run_rfm_scoring(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.dropna(subset=["customer_id", "created_at", amount_col])

    ref_date = df["created_at"].max() + pd.Timedelta(days=1)

    # Per-customer aggregation
    cust = df.groupby("customer_id").agg(
        recency=("created_at", lambda x: (ref_date - x.max()).days),
        frequency=("created_at", "count"),
        monetary=(amount_col, "sum"),
    ).reset_index()

    # Score 1-5 using quintiles (handle duplicate bin edges)
    for col, label in [("recency", "R"), ("frequency", "F"), ("monetary", "M")]:
        try:
            if label == "R":
                # Lower recency = better → invert labels
                cust[label] = pd.qcut(cust[col], 5, labels=[5, 4, 3, 2, 1], duplicates="drop").astype(int)
            else:
                cust[label] = pd.qcut(cust[col], 5, labels=[1, 2, 3, 4, 5], duplicates="drop").astype(int)
        except ValueError:
            # Not enough unique values for 5 bins
            cust[label] = 3

    cust["rfm_score"] = cust["R"].astype(str) + cust["F"].astype(str) + cust["M"].astype(str)
    cust["segment"] = cust.apply(lambda row: _assign_segment(row["R"], row["F"], row["M"]), axis=1)

    # ── Update customers table ──────────────────────────────────────────
    values = [(row["customer_id"], row["rfm_score"], row["segment"]) for _, row in cust.iterrows()]
    if values:
        # Batch update via temp table approach
        for cid, score, seg in values:
            session.execute(
                text("""
                    UPDATE customers
                    SET rfm_score = :score, rfm_segment = :seg, updated_at = NOW()
                    WHERE external_id = :cid
                """),
                {"score": score, "seg": seg, "cid": cid},
            )
        session.commit()

    # ── Build result JSON ───────────────────────────────────────────────
    seg_summary = cust.groupby("segment").agg(
        count=("customer_id", "count"),
        avg_monetary=("monetary", "mean"),
    ).reset_index()
    seg_summary["pct"] = (seg_summary["count"] / len(cust) * 100).round(2)
    segments = seg_summary.rename(columns={"segment": "name"}).to_dict("records")

    # Score distribution
    score_dist = cust["rfm_score"].value_counts().head(20).reset_index()
    score_dist.columns = ["score", "count"]
    distribution = score_dist.to_dict("records")

    # Top customers by monetary
    top = cust.nlargest(20, "monetary")[["customer_id", "rfm_score", "segment", "monetary", "frequency", "recency"]]
    top_customers = top.to_dict("records")

    return {
        "segments": segments,
        "distribution": distribution,
        "top_customers": top_customers,
        "total_customers": len(cust),
    }
