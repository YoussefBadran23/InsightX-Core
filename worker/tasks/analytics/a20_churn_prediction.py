"""A20 — Churn Risk Prediction (Logistic Regression).

Predicts churn probability per customer based on behavioral features.
Uses temporal split to avoid data leakage: features are computed from the
observation window, churn labels from the holdout window.
Updates customers.churn_risk_score (0.0-1.0).
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sqlalchemy import text
from ._base import analytics_task, has_col


def _build_features(txn_df, amount_col, ref_date):
    """Build behavioural features from transaction data.

    Features are designed to be available BEFORE the prediction date,
    so they never leak future information.
    """
    cust = txn_df.groupby("customer_id").agg(
        frequency=("created_at", "count"),
        monetary=(amount_col, "sum"),
        avg_order_value=(amount_col, "mean"),
        std_order_value=(amount_col, "std"),
        recency=("created_at", lambda x: (ref_date - x.max()).days),
        tenure=("created_at", lambda x: (ref_date - x.min()).days),
        order_span=("created_at", lambda x: (x.max() - x.min()).days),
    ).reset_index()

    # Derived features (no leakage — all from observation window)
    cust["std_order_value"] = cust["std_order_value"].fillna(0)
    cust["avg_days_between_orders"] = (
        cust["order_span"] / cust["frequency"].clip(lower=2)
    ).fillna(0)
    cust["purchase_regularity"] = (
        cust["std_order_value"] / cust["avg_order_value"].clip(lower=0.01)
    ).clip(upper=10)
    cust["orders_per_tenure"] = (
        cust["frequency"] / cust["tenure"].clip(lower=1) * 30
    )  # monthly purchase rate
    cust["monetary_per_tenure"] = (
        cust["monetary"] / cust["tenure"].clip(lower=1) * 30
    )

    return cust


@analytics_task("A20_churn_prediction", "churn")
def run_churn_prediction(df, session, job_id):
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", "created_at", amount_col])

    total_span = (df["created_at"].max() - df["created_at"].min()).days
    if total_span < 30 or len(df) < 50:
        return {
            "risk_distribution": [],
            "summary": "Not enough data span for churn prediction",
            "total_customers": 0,
        }

    # ── Temporal split to prevent data leakage ──────────────────────────
    # Observation window: first 70% of timeline → build features
    # Holdout window:     last  30% of timeline → define churn labels
    cutoff = df["created_at"].min() + pd.Timedelta(days=int(total_span * 0.7))
    obs_df = df[df["created_at"] <= cutoff]
    holdout_df = df[df["created_at"] > cutoff]

    holdout_days = (df["created_at"].max() - cutoff).days
    churn_threshold = max(30, holdout_days // 2)

    # Build features from observation window only
    cust = _build_features(obs_df, amount_col, cutoff)

    # Churn label: did the customer buy in the holdout window?
    active_in_holdout = set(holdout_df["customer_id"].unique())
    cust["is_churned"] = (~cust["customer_id"].isin(active_in_holdout)).astype(int)

    if len(cust) < 20:
        return {
            "risk_distribution": [],
            "summary": "Not enough customers for churn prediction",
            "total_customers": len(cust),
        }

    # ── Feature selection (NO recency — it would leak the label) ────────
    # We exclude 'recency' because: churn = didn't buy in holdout, and
    # recency measures how long since last observation-window purchase.
    # Including it would create a near-perfect but useless predictor.
    feature_cols = [
        "frequency", "monetary", "avg_order_value", "std_order_value",
        "tenure", "order_span", "avg_days_between_orders",
        "purchase_regularity", "orders_per_tenure", "monetary_per_tenure",
    ]
    X = cust[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
    y = cust["is_churned"]

    if y.nunique() < 2:
        cust["churn_risk_score"] = 0.5
    else:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # ── Hyperparameter tuning via cross-validation ──────────────────
        best_c, best_f1 = 1.0, 0
        cv = StratifiedKFold(n_splits=min(5, max(2, int(y.sum()))), shuffle=True, random_state=42)

        for c in [0.01, 0.1, 0.5, 1.0, 5.0, 10.0]:
            model = LogisticRegression(
                C=c, max_iter=1000, random_state=42,
                class_weight="balanced", solver="lbfgs",
            )
            try:
                scores = cross_val_score(model, X_scaled, y, cv=cv, scoring="f1")
                mean_f1 = scores.mean()
                if mean_f1 > best_f1:
                    best_f1 = mean_f1
                    best_c = c
            except Exception:
                continue

        # Train final model with best C
        final_model = LogisticRegression(
            C=best_c, max_iter=1000, random_state=42,
            class_weight="balanced", solver="lbfgs",
        )
        final_model.fit(X_scaled, y)

        # ── Score ALL customers (using full data for production) ────────
        # Rebuild features using full timeline for the final scoring pass
        ref_date = df["created_at"].max() + pd.Timedelta(days=1)
        full_cust = _build_features(df, amount_col, ref_date)
        X_full = full_cust[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        X_full_scaled = scaler.transform(X_full)
        full_cust["churn_risk_score"] = final_model.predict_proba(X_full_scaled)[:, 1].round(4)

        # Merge back
        cust = full_cust

    # ── Update customers table (bulk update for performance) ────────────
    updates = [
        {"score": float(row["churn_risk_score"]), "cid": row["customer_id"]}
        for _, row in cust.iterrows()
    ]
    if updates:
        session.execute(
            text("""
                UPDATE customers
                SET churn_risk_score = :score, updated_at = NOW()
                WHERE external_id = :cid
            """),
            updates,
        )
    session.commit()

    # ── Risk distribution (buckets) ─────────────────────────────────────
    bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
    labels = ["Very Low", "Low", "Medium", "High", "Very High"]
    cust["risk_bucket"] = pd.cut(
        cust["churn_risk_score"], bins=bins, labels=labels, include_lowest=True
    )

    risk_dist = cust.groupby("risk_bucket", observed=True).agg(
        count=("customer_id", "count"),
        avg_monetary=("monetary", "mean"),
    ).reset_index()
    risk_dist["pct"] = (risk_dist["count"] / len(cust) * 100).round(2)

    top_risk = cust.nlargest(20, "churn_risk_score")[
        ["customer_id", "churn_risk_score", "frequency", "monetary", "avg_days_between_orders"]
    ].to_dict("records")

    return {
        "risk_distribution": risk_dist.to_dict("records"),
        "top_at_risk": top_risk,
        "total_customers": len(cust),
        "churn_rate": round(float(cust.get("is_churned", pd.Series([0])).mean()) * 100, 2),
        "churn_threshold_days": churn_threshold,
        "model_params": {"C": best_c if y.nunique() >= 2 else None, "cv_f1": round(best_f1, 4) if y.nunique() >= 2 else None},
        "features_used": feature_cols,
    }
