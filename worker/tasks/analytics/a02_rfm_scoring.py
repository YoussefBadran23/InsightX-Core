"""A02 — RFM Scoring (Optimized)."""
import pandas as pd
from sqlalchemy import text
from ._base import analytics_task, has_col

# RAM Optimization
COLS = ["customer_id", "created_at", "total_amount", "net_amount"]

_RFM_SEGMENTS = {
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

def _assign_segment(r, f, m):
    for name, rule in _RFM_SEGMENTS.items():
        if rule(r, f, m): return name
    return "Other"

@analytics_task("A02_rfm_scoring", "rfm", required_cols=COLS)
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

    # Optimized Quintile Scoring
    for col, label in [("recency", "R"), ("frequency", "F"), ("monetary", "M")]:
        try:
            bins = [5, 4, 3, 2, 1] if label == "R" else [1, 2, 3, 4, 5]
            cust[label] = pd.qcut(cust[col], 5, labels=bins, duplicates="drop").astype(int)
        except ValueError:
            cust[label] = 3

    cust["rfm_score"] = cust["R"].astype(str) + cust["F"].astype(str) + cust["M"].astype(str)
    cust["segment"] = cust.apply(lambda x: _assign_segment(x["R"], x["F"], x["M"]), axis=1)

    # PERFORMANCE WIN: Batch Update
    batch_data = [{"score": r.rfm_score, "seg": r.segment, "cid": r.customer_id} for r in cust.itertuples()]
    if batch_data:
        session.execute(
            text("UPDATE customers SET rfm_score = :score, rfm_segment = :seg, updated_at = NOW() WHERE external_id = :cid"),
            batch_data
        )
        session.commit()

    return {
        "segments": cust.groupby("segment").size().reset_index(name='count').to_dict("records"),
        "top_customers": cust.nlargest(20, "monetary").to_dict("records"),
        "total_customers": len(cust),
    }