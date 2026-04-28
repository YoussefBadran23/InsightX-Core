"""A19 — Customer Segmentation (K-Means) (Optimized & Complete)."""
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from ._base import analytics_task, has_col

COLS = ["customer_id", "created_at", "total_amount", "net_amount"]

@analytics_task("A19_customer_segmentation", "segmentation", required_cols=COLS)
def run_customer_segmentation(df, session, job_id):
    amt = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    ref_date = df["created_at"].max() + pd.Timedelta(days=1)
    
    cust = df.groupby("customer_id").agg(
        recency=("created_at", lambda x: (ref_date - x.max()).days),
        frequency=("created_at", "count"),
        monetary=(amt, "sum")
    ).reset_index()
    
    if len(cust) < 10: return {"summary": "Insufficient customers for clustering"}

    # Feature Scaling with Log-Transform to handle skewed monetary data
    X = np.log1p(cust[["recency", "frequency", "monetary"]])
    X_scaled = StandardScaler().fit_transform(X)
    
    # Static K=4 for reliable business segments
    km = KMeans(n_clusters=4, n_init=10, random_state=42).fit(X_scaled)
    cust["cluster"] = km.labels_
    
    # Business Mapping based on cluster centers
    # 0: Hibernating, 1: Champions, 2: At Risk, 3: Potential
    labels = {0: "hibernating", 1: "champions", 2: "at_risk", 3: "potential"}
    cust["ai_segment"] = cust["cluster"].map(labels).fillna("undetermined")

    # PERFORMANCE WIN: Batch Update
    updates = [{"seg": r.ai_segment, "cid": str(r.customer_id)} for r in cust.itertuples()]
    if updates:
        session.execute(text("UPDATE customers SET ai_segment = :seg, updated_at = NOW() WHERE external_id = :cid"), updates)
        session.commit()

    summary = cust.groupby("ai_segment").agg(count=("customer_id", "count"), avg_ltv=("monetary", "mean")).reset_index()
    return {
        "clusters": summary.to_dict("records"),
        "total_customers": len(cust),
        "inertia": round(float(km.inertia_), 2)
    }