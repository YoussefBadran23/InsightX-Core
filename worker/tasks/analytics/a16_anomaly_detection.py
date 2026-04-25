"""A16 — Anomaly Detection (Isolation Forest).

Identifies outlier orders based on amount, quantity, and timing features.
Adaptive contamination based on IQR-derived expected anomaly rate.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from ._base import analytics_task, has_col


def _estimate_contamination(values):
    """Estimate expected anomaly rate from data using IQR method.

    Instead of a fixed percentage, this examines the actual distribution
    and estimates what fraction falls beyond 3x IQR — a data-driven
    contamination parameter.
    """
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    if iqr == 0:
        return 0.01  # default for constant data

    upper_fence = q3 + 3.0 * iqr
    lower_fence = q1 - 3.0 * iqr
    outlier_frac = np.mean((values > upper_fence) | (values < lower_fence))

    # Clamp to [0.5%, 5%] — below 0.5% misses real anomalies,
    # above 5% flags too much noise
    return float(np.clip(outlier_frac, 0.005, 0.05))


@analytics_task("A16_anomaly_detection", "anomaly")
def run_anomaly_detection(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=[amount_col])

    # ── Richer feature matrix ───────────────────────────────────────────
    feature_cols = [amount_col]
    if has_col(df, "quantity"):
        feature_cols.append("quantity")
    if has_col(df, "discount_amount"):
        feature_cols.append("discount_amount")

    # Derived features for better anomaly separation
    df = df.copy()
    if "quantity" in df.columns and amount_col in df.columns:
        df["unit_price_derived"] = (
            df[amount_col] / df["quantity"].replace(0, np.nan)
        ).fillna(0)
        feature_cols.append("unit_price_derived")

    X = df[feature_cols].fillna(0).copy()
    X = X.replace([np.inf, -np.inf], 0)

    if len(X) < 20:
        return {
            "anomalies": [],
            "summary": "Not enough data for anomaly detection",
            "total_orders": len(df),
        }

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── Adaptive contamination from data distribution ───────────────────
    contamination = _estimate_contamination(df[amount_col].values)

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        max_samples=min(len(X), 10000),  # subsample for speed on large data
        max_features=min(len(feature_cols), 3),
        random_state=42,
    )
    df["anomaly_label"] = model.fit_predict(X_scaled)
    df["anomaly_score"] = -model.decision_function(X_scaled)

    # -1 = anomaly, 1 = normal
    anomalies = df[df["anomaly_label"] == -1].copy()
    normal = df[df["anomaly_label"] == 1]

    # Build anomaly detail (top 50 by score)
    top_anomalies = anomalies.nlargest(50, "anomaly_score")
    anomaly_records = []
    for _, row in top_anomalies.iterrows():
        rec = {
            "amount": float(row.get(amount_col, 0)),
            "anomaly_score": round(float(row["anomaly_score"]), 4),
        }
        if has_col(df, "id"):
            rec["order_id"] = str(row.get("id", ""))
        if has_col(df, "customer_id"):
            rec["customer_id"] = str(row.get("customer_id", ""))
        if has_col(df, "created_at"):
            rec["date"] = str(row.get("created_at", ""))
        if has_col(df, "quantity"):
            rec["quantity"] = int(row.get("quantity", 0))
        anomaly_records.append(rec)

    return {
        "anomalies": anomaly_records,
        "total_orders": len(df),
        "anomaly_count": len(anomalies),
        "anomaly_pct": round(len(anomalies) / len(df) * 100, 2),
        "contamination_used": round(contamination, 4),
        "normal_avg_amount": round(float(normal[amount_col].mean()), 2) if len(normal) > 0 else 0,
        "anomaly_avg_amount": round(float(anomalies[amount_col].mean()), 2) if len(anomalies) > 0 else 0,
        "features_used": feature_cols,
    }
