"""A19 — Customer Segmentation (K-Means).

Clusters customers based on RFM features using K-Means.
Automatically selects the optimal k (2-8) via silhouette score.
Log-transforms skewed monetary/frequency to prevent outlier dominance.
Updates customers.ai_segment with cluster labels.
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from sqlalchemy import text
from ._base import analytics_task, has_col


def _label_clusters(centers, labels_array, n_clusters):
    """Map cluster indices to business-meaningful labels.

    Uses a composite score that accounts for RFM semantics:
    - Low recency = better (more recent)
    - High frequency = better
    - High monetary = better

    The centers are in scaled space, so we invert recency (col 0) before ranking.
    """
    # Invert recency column so lower recency → higher score
    adjusted = centers.copy()
    adjusted[:, 0] = -adjusted[:, 0]  # recency: lower is better
    center_scores = adjusted.sum(axis=1)
    rank = np.argsort(-center_scores)  # descending by value

    available = ["vip_champion", "loyalist", "new_potential", "at_risk", "undetermined"]
    mapping = {}
    for i, cluster_idx in enumerate(rank):
        mapping[cluster_idx] = available[i] if i < len(available) else "undetermined"

    return np.array([mapping[l] for l in labels_array])


def _find_optimal_k(scaled, k_min=2, k_max=8):
    """Select optimal k by maximising silhouette score.

    Returns (best_k, {k: silhouette_score}).
    """
    n_samples = len(scaled)
    k_max = min(k_max, n_samples - 1)
    k_min = max(k_min, 2)

    scores = {}
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(scaled)
        scores[k] = silhouette_score(scaled, labels)

    best_k = max(scores, key=scores.get)

    # Penalty for too-few clusters: if k=2 wins by < 0.05 over k=3/4, prefer
    # the higher k for business utility (more actionable segments)
    if best_k == 2 and len(scores) > 1:
        next_best = sorted(scores.items(), key=lambda x: -x[1])
        if len(next_best) > 1:
            runner_up_k, runner_up_score = next_best[1]
            if runner_up_k >= 3 and (scores[2] - runner_up_score) < 0.05:
                best_k = runner_up_k

    return best_k, scores


@analytics_task("A19_customer_segmentation", "segmentation")
def run_customer_segmentation(df, session, job_id):
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", "created_at", amount_col])

    ref_date = df["created_at"].max() + pd.Timedelta(days=1)

    cust = df.groupby("customer_id").agg(
        recency=("created_at", lambda x: (ref_date - x.max()).days),
        frequency=("created_at", "count"),
        monetary=(amount_col, "sum"),
    ).reset_index()

    if len(cust) < 8:
        return {
            "clusters": [],
            "summary": "Not enough customers for segmentation",
            "total_customers": len(cust),
        }

    # ── Log-transform skewed features ───────────────────────────────────
    # Monetary and frequency are typically power-law distributed.
    # Log1p prevents outlier dominance and makes K-Means more effective.
    features = cust[["recency", "frequency", "monetary"]].fillna(0).copy()
    features["frequency"] = np.log1p(features["frequency"])
    features["monetary"] = np.log1p(features["monetary"])

    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)

    # ── Automatic k selection ───────────────────────────────────────────
    best_k, sil_scores = _find_optimal_k(scaled, k_min=2, k_max=min(8, len(cust) - 1))

    km = KMeans(n_clusters=best_k, n_init=10, random_state=42)
    cust["cluster"] = km.fit_predict(scaled)

    final_silhouette = silhouette_score(scaled, cust["cluster"])

    # Assign meaningful labels based on cluster centers
    cust["ai_segment"] = _label_clusters(km.cluster_centers_, cust["cluster"].values, best_k)

    # ── Update customers table (bulk update for performance) ────────────
    updates = [
        {"seg": row["ai_segment"], "cid": row["customer_id"]}
        for _, row in cust.iterrows()
    ]
    if updates:
        session.execute(
            text("""
                UPDATE customers
                SET ai_segment = :seg, updated_at = NOW()
                WHERE external_id = :cid
            """),
            updates,
        )
    session.commit()

    # ── Build result JSON ───────────────────────────────────────────────
    cluster_summary = cust.groupby("ai_segment").agg(
        count=("customer_id", "count"),
        avg_recency=("recency", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
    ).reset_index()
    cluster_summary["pct"] = (cluster_summary["count"] / len(cust) * 100).round(2)

    scatter_sample = cust.sample(min(500, len(cust)), random_state=42)
    scatter_data = scatter_sample[
        ["customer_id", "monetary", "frequency", "recency", "ai_segment"]
    ].rename(
        columns={"monetary": "lifetime_value", "frequency": "total_orders"}
    ).to_dict("records")

    return {
        "clusters": cluster_summary.to_dict("records"),
        "scatter_data": scatter_data,
        "total_customers": len(cust),
        "n_clusters": best_k,
        "silhouette_score": round(float(final_silhouette), 4),
        "inertia": round(float(km.inertia_), 2),
        "k_selection": {str(k): round(s, 4) for k, s in sil_scores.items()},
    }
