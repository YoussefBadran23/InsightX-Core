"""A19 — Customer Segmentation (K-Means on log-RFM features).

Unsupervised clustering of customers into K=4 behavioral segments. Unlike
A02 (RFM scoring), which uses fixed quintile rules and named segments
("Champions / Loyal / At Risk / ..."), this module discovers the natural
clusters in the dataset and labels them by their centroid characteristics.

Pipeline
--------
1. Build per-customer RFM table: recency_days, frequency, monetary.
2. log1p-transform features to compress the heavy right tail of monetary
   (the standard pre-processing for RFM K-Means — without it, a handful
   of whale customers pull the centroids and everyone else collapses).
3. StandardScale (zero mean, unit variance).
4. Fit KMeans(k=4, random_state=42) — deterministic across runs.
5. Compute centroid statistics in original (not scaled) feature space.
6. Map cluster_id → human label by ranking centroids:
   - highest monetary + high frequency + low recency → "champions"
   - high frequency + medium monetary               → "loyal"
   - low frequency + high recency                  → "at_risk"
   - middle of pack                                → "promising"

Required columns:  customer_id, order_date, total_amount
Optional columns:  net_amount

Output schema::

    {
      "summary": {
        "n_customers":        int,
        "snapshot_date":      "YYYY-MM-DD",
        "n_clusters":         int,
        "method":             str,
        "silhouette_score":   float | null,
        "scaler":             "StandardScaler",
        "random_state":       42
      },
      "clusters": [
        {
          "cluster_id":     int,
          "label":          "champions"|"loyal"|"at_risk"|"promising",
          "name":           str,
          "count":          int,
          "pct":            float,
          "centroid":       {"recency_days": float, "frequency": float, "monetary": float},
          "avg_monetary":   float,
          "total_revenue":  float,
          "rev_pct":        float
        }
      ],
      "top_customers_per_cluster": [
        {"cluster_id": int, "label": str, "customers": [
           {"customer_id": str, "recency_days": int, "frequency": int,
            "monetary": float, "distance_to_centroid": float}
        ]}
      ],
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


N_CLUSTERS = 4
MIN_CUSTOMERS = 20
TOP_PER_CLUSTER = 10
RANDOM_STATE = 42


def _label_clusters_by_centroid(centroids: np.ndarray) -> dict[int, str]:
    """Map cluster_id → human label by ranking centroids in (recency, freq, monetary) space.

    Centroids are in the ORIGINAL (un-scaled, un-log) feature space:
    columns are [recency_days, frequency, monetary].
    """
    # Composite score: high monetary + high frequency - high recency (recency low = good)
    # Normalize each feature to [0, 1] before combining so scales don't dominate.
    cs = centroids.copy().astype(float)
    n = cs.shape[0]
    rng = cs.max(axis=0) - cs.min(axis=0)
    rng[rng == 0] = 1.0
    norm = (cs - cs.min(axis=0)) / rng  # 0..1 per feature
    # invert recency (lower = better)
    norm[:, 0] = 1 - norm[:, 0]
    score = norm[:, 0] + norm[:, 1] + norm[:, 2]  # higher = better customer
    ranked = np.argsort(-score)  # best → worst

    labels: list[str]
    if n == 4:
        labels = ["champions", "loyal", "promising", "at_risk"]
    elif n == 3:
        labels = ["champions", "loyal", "at_risk"]
    elif n == 2:
        labels = ["champions", "at_risk"]
    else:
        labels = [f"cluster_{i}" for i in range(n)]

    return {int(ranked[i]): labels[i] for i in range(n)}


_LABEL_TO_NAME = {
    "champions": "Champions",
    "loyal": "Loyal",
    "promising": "Promising",
    "at_risk": "At Risk",
}


@register(
    key="A19_customer_segmentation",
    analysis_type="customer",
    required_cols=["customer_id", "order_date", "total_amount"],
    optional_cols=["net_amount"],
    description="K-Means clustering on log-RFM features (k=4).",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import silhouette_score
    except ImportError:
        return _empty("scikit-learn not installed")

    df = df.copy()
    df["order_date"] = coerce_date(df["order_date"])
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])

    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", "order_date", amount_col])
    df = df[df[amount_col] >= 0]
    df["customer_id"] = df["customer_id"].astype(str)

    if df.empty or df["customer_id"].nunique() < MIN_CUSTOMERS:
        return _empty(
            f"only {df['customer_id'].nunique()} customers — K-Means needs ≥{MIN_CUSTOMERS}"
        )

    snapshot = df["order_date"].max()

    # ── Per-customer RFM ────────────────────────────────────────────────────
    rfm = df.groupby("customer_id").agg(
        recency_days=("order_date", lambda s: int((snapshot - s.max()).days)),
        frequency=("order_date", "count"),
        monetary=(amount_col, "sum"),
    ).reset_index()

    n_customers = int(len(rfm))

    # ── Feature engineering: log1p then StandardScale ──────────────────────
    raw = rfm[["recency_days", "frequency", "monetary"]].astype(float).values
    feats = np.log1p(raw)
    scaler = StandardScaler()
    feats_scaled = scaler.fit_transform(feats)

    # Pick k = min(N_CLUSTERS, n_customers // 5) — need enough customers per cluster.
    k = min(N_CLUSTERS, max(2, n_customers // 5))

    km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
    rfm["cluster_id"] = km.fit_predict(feats_scaled)

    # Silhouette — quality metric (range -1..1, higher is better).
    try:
        sil = float(silhouette_score(feats_scaled, rfm["cluster_id"], sample_size=min(5000, n_customers)))
    except Exception:
        sil = None

    # Centroids in ORIGINAL (un-log, un-scaled) space — easier to interpret.
    centroids_scaled = km.cluster_centers_
    centroids_log = scaler.inverse_transform(centroids_scaled)
    centroids = np.expm1(centroids_log)  # invert log1p

    label_map = _label_clusters_by_centroid(centroids)
    rfm["label"] = rfm["cluster_id"].map(label_map)
    rfm["name"] = rfm["label"].map(_LABEL_TO_NAME).fillna(rfm["label"])

    # Distance from each customer to its cluster centroid (in scaled space).
    distances = np.linalg.norm(
        feats_scaled - centroids_scaled[rfm["cluster_id"].values], axis=1
    )
    rfm["distance_to_centroid"] = distances

    # ── Cluster summary table ───────────────────────────────────────────────
    total_rev = float(rfm["monetary"].sum())
    cluster_rows = []
    for cid in sorted(rfm["cluster_id"].unique()):
        sub = rfm[rfm["cluster_id"] == cid]
        c = centroids[int(cid)]
        cluster_rows.append({
            "cluster_id": int(cid),
            "label": str(label_map.get(int(cid), f"cluster_{cid}")),
            "name": _LABEL_TO_NAME.get(label_map.get(int(cid), ""), f"Cluster {cid}"),
            "count": int(len(sub)),
            "pct": round(len(sub) / n_customers * 100, 2),
            "centroid": {
                "recency_days": round(float(c[0]), 2),
                "frequency": round(float(c[1]), 2),
                "monetary": round(float(c[2]), 2),
            },
            "avg_recency_days": round(float(sub["recency_days"].mean()), 2),
            "avg_frequency": round(float(sub["frequency"].mean()), 2),
            "avg_monetary": round(float(sub["monetary"].mean()), 2),
            "total_revenue": round(float(sub["monetary"].sum()), 2),
            "rev_pct": round(float(sub["monetary"].sum()) / total_rev * 100, 2) if total_rev > 0 else 0.0,
        })

    cluster_rows.sort(key=lambda r: r["avg_monetary"], reverse=True)

    # ── Top customers per cluster (closest to centroid) ─────────────────────
    top_per_cluster = []
    for cid in sorted(rfm["cluster_id"].unique()):
        sub = rfm[rfm["cluster_id"] == cid].nsmallest(TOP_PER_CLUSTER, "distance_to_centroid")
        top_per_cluster.append({
            "cluster_id": int(cid),
            "label": str(label_map.get(int(cid), f"cluster_{cid}")),
            "customers": [
                {
                    "customer_id": str(r["customer_id"]),
                    "recency_days": int(r["recency_days"]),
                    "frequency": int(r["frequency"]),
                    "monetary": round(float(r["monetary"]), 2),
                    "distance_to_centroid": round(float(r["distance_to_centroid"]), 4),
                }
                for r in sub.to_dict("records")
            ],
        })

    return {
        "summary": {
            "n_customers": n_customers,
            "snapshot_date": snapshot.date().isoformat(),
            "n_clusters": int(k),
            "method": "K-Means + log1p + StandardScaler",
            "silhouette_score": round(sil, 4) if sil is not None else None,
            "scaler": "StandardScaler",
            "random_state": RANDOM_STATE,
        },
        "clusters": cluster_rows,
        "top_customers_per_cluster": top_per_cluster,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_customers": 0, "snapshot_date": None,
            "n_clusters": 0, "method": "K-Means + log1p + StandardScaler",
            "silhouette_score": None, "scaler": "StandardScaler",
            "random_state": RANDOM_STATE,
        },
        "clusters": [],
        "top_customers_per_cluster": [],
        "warning": warning,
    }
