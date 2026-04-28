"""A16 — Anomaly Detection (Optimized & Complete)."""
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from ._base import analytics_task, has_col

COLS = ["total_amount", "net_amount", "quantity", "discount_amount", "id", "customer_id", "created_at"]

def _estimate_contamination(values):
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    if iqr == 0: return 0.01
    outlier_frac = np.mean((values > q3 + 3*iqr) | (values < q1 - 3*iqr))
    return float(np.clip(outlier_frac, 0.005, 0.05))

@analytics_task("A16_anomaly_detection", "anomaly", required_cols=COLS)
def run_anomaly_detection(df, session, job_id):
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=[amount_col]).copy()
    df["unit_price"] = (df[amount_col] / df["quantity"].replace(0, np.nan)).fillna(0)
    
    features = [amount_col, "unit_price"]
    if has_col(df, "quantity"): features.append("quantity")
    
    X = df[features].replace([np.inf, -np.inf], 0).fillna(0)
    if len(X) < 20: return {"summary": "Insufficient data"}

    X_scaled = StandardScaler().fit_transform(X)
    contam = _estimate_contamination(df[amount_col].values)
    
    model = IsolationForest(n_estimators=100, contamination=contam, random_state=42)
    df["anomaly_score"] = -model.decision_function(X_scaled)
    df["is_anomaly"] = model.predict(X_scaled) == -1

    anomalies = df[df["is_anomaly"]].nlargest(50, "anomaly_score")
    
    return {
        "anomalies": anomalies.assign(amount=lambda x: x[amount_col].astype(float), 
                                      score=lambda x: x.anomaly_score.round(4)).to_dict("records"),
        "anomaly_pct": round(df["is_anomaly"].mean() * 100, 2),
        "contamination": round(contam, 4)
    }