"""A20 — Churn Risk Prediction (Logistic Regression).

Supervised classification: predict the probability each customer will churn
in the next window, where "churn" is defined as no purchase in the past
`CHURN_THRESHOLD_DAYS` (default 90) days at the snapshot date.

Approach
--------
1. Build per-customer feature table: recency, frequency, monetary, lifespan,
   avg_inter_purchase_days, days_since_first_order.
2. Label each customer as churned (1) or active (0) using a snapshot-date
   cutoff: snapshot - CHURN_THRESHOLD_DAYS.
3. Re-anchor each customer's features to a "training snapshot" earlier
   than the real snapshot, so we have known future behaviour to learn from.
   We split: features computed up to (snapshot - 90d), label computed
   between that cutoff and snapshot.
4. Train sklearn LogisticRegression with class_weight='balanced' (churn
   is the minority class on most datasets — the balancing prevents the
   model from collapsing to "always predict active").
5. Predict churn_probability for ALL customers using their CURRENT
   features. This is what the dashboard surfaces.

Required columns:  customer_id, order_date, total_amount
Optional columns:  net_amount

Output schema::

    {
      "summary": {
        "n_customers":               int,
        "snapshot_date":             "YYYY-MM-DD",
        "churn_threshold_days":      int,
        "n_churned_historical":      int,
        "churn_rate_historical_pct": float,
        "avg_churn_risk":            float,    # mean predicted probability
        "model_accuracy":            float,    # train/test split holdout
        "model_method":              "Logistic Regression (class_weight=balanced)"
      },
      "risk_buckets": [
        {"bucket": "low (0-20%)",       "count": int, "pct": float},
        {"bucket": "medium (20-50%)",   "count": int, "pct": float},
        {"bucket": "high (50-80%)",     "count": int, "pct": float},
        {"bucket": "critical (80%+)",   "count": int, "pct": float}
      ],
      "feature_importance": [
        {"feature": str, "coefficient": float, "abs_importance": float}
      ],
      "top_at_risk": [
        {"customer_id": str, "churn_probability": float,
         "recency_days": int, "frequency": int, "monetary": float,
         "lifespan_days": int}
      ],
      "warning": str | null
    }
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "Which of my loyal customers are about to leave me?"

CHURN_THRESHOLD_DAYS = 90
MIN_CUSTOMERS = 50
MIN_CHURNED_FOR_TRAIN = 10
TOP_N_AT_RISK = 25


def _per_customer_features(df: pd.DataFrame, snapshot: pd.Timestamp,
                            amount_col: str) -> pd.DataFrame:
    """Aggregate orders into per-customer feature rows. Snapshot is the
    'now' anchor for recency / days-since-first-order calculations."""
    g = df.groupby("customer_id")
    out = pd.DataFrame({
        "customer_id":           g["order_date"].max().index,
        "last_order":            g["order_date"].max().values,
        "first_order":           g["order_date"].min().values,
        "frequency":             g["order_date"].count().values,
        "monetary":              g[amount_col].sum().values,
    })
    out["recency_days"]   = (snapshot - pd.to_datetime(out["last_order"])).dt.days
    out["lifespan_days"]  = (pd.to_datetime(out["last_order"]) - pd.to_datetime(out["first_order"])).dt.days
    out["days_since_first"] = (snapshot - pd.to_datetime(out["first_order"])).dt.days
    # avg inter-purchase: lifespan / max(frequency-1, 1). One-time buyers get
    # lifespan_days = 0 → use days_since_first as a fallback proxy.
    out["avg_inter_purchase_days"] = np.where(
        out["frequency"] > 1,
        out["lifespan_days"] / (out["frequency"] - 1).clip(lower=1),
        out["days_since_first"],
    )
    out["frequency"]     = out["frequency"].astype(int)
    out["recency_days"]  = out["recency_days"].astype(int)
    out["lifespan_days"] = out["lifespan_days"].astype(int)
    out["days_since_first"] = out["days_since_first"].astype(int)
    return out


@register(
    key="A20_churn_prediction",
    analysis_type="customer",
    required_cols=["customer_id", "order_date", "total_amount"],
    optional_cols=["net_amount"],
    description="Logistic Regression churn probability per customer.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score
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
            f"only {df['customer_id'].nunique()} customers — churn model needs ≥{MIN_CUSTOMERS}"
        )

    snapshot = df["order_date"].max()
    train_cutoff = snapshot - pd.Timedelta(days=CHURN_THRESHOLD_DAYS)

    # ── Training data: features from BEFORE the cutoff, labels from AFTER ──
    train_orders = df[df["order_date"] <= train_cutoff]
    if train_orders.empty or train_orders["customer_id"].nunique() < MIN_CHURNED_FOR_TRAIN * 4:
        return _empty(
            "not enough historical window — need ≥90 days of pre-snapshot data to train"
        )

    train_features = _per_customer_features(train_orders, train_cutoff, amount_col)

    # Did they purchase after the cutoff? If yes, label = 0 (active). Else 1 (churned).
    post_cutoff_customers = set(
        df[df["order_date"] > train_cutoff]["customer_id"].unique()
    )
    train_features["churned"] = (~train_features["customer_id"].isin(post_cutoff_customers)).astype(int)

    n_churned = int(train_features["churned"].sum())
    n_active_in_train = len(train_features) - n_churned

    # ── Heuristic fallback ──────────────────────────────────────────────────
    # Some datasets (one-time-buyer-heavy) have degenerate labels: either
    # everyone bought again (no churn signal) or nobody did (all churn). ML
    # can't learn anything from that. We fall back to a survival-style
    # recency decay: P(churn) = 1 - exp(-(recency - grace) / scale).
    # Reported honestly as `model_method = "Recency heuristic"` so the
    # dashboard distinguishes it from a real ML fit.
    if n_churned < MIN_CHURNED_FOR_TRAIN or n_active_in_train < MIN_CHURNED_FOR_TRAIN:
        return _heuristic_score(df, snapshot, amount_col, n_churned)

    feature_cols = [
        "recency_days", "frequency", "monetary",
        "lifespan_days", "days_since_first", "avg_inter_purchase_days",
    ]
    X_train_raw = train_features[feature_cols].astype(float).values
    y_train = train_features["churned"].values

    # log1p to compress monetary skew, then StandardScale.
    X_train_log = np.log1p(np.clip(X_train_raw, a_min=0, a_max=None))
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_log)

    # Holdout 20% to report a model_accuracy that isn't training-data accuracy.
    test_acc = None
    if len(y_train) >= 50 and y_train.sum() > 5 and (len(y_train) - y_train.sum()) > 5:
        try:
            X_tr, X_te, y_tr, y_te = train_test_split(
                X_train, y_train, test_size=0.2, random_state=42, stratify=y_train,
            )
            model_holdout = LogisticRegression(class_weight="balanced", max_iter=500)
            model_holdout.fit(X_tr, y_tr)
            test_acc = float(accuracy_score(y_te, model_holdout.predict(X_te)))
        except Exception:
            test_acc = None

    # Train final model on all training data.
    model = LogisticRegression(class_weight="balanced", max_iter=500)
    model.fit(X_train, y_train)

    # ── Predict probabilities for ALL current customers ──────────────────────
    current = _per_customer_features(df, snapshot, amount_col)
    X_cur_raw = current[feature_cols].astype(float).values
    X_cur = scaler.transform(np.log1p(np.clip(X_cur_raw, a_min=0, a_max=None)))
    probs = model.predict_proba(X_cur)[:, 1]  # P(churn)
    current["churn_probability"] = np.round(probs, 4)

    n_customers = int(len(current))

    # ── Risk buckets ────────────────────────────────────────────────────────
    buckets = [
        ("low (0-20%)",      0.00, 0.20),
        ("medium (20-50%)",  0.20, 0.50),
        ("high (50-80%)",    0.50, 0.80),
        ("critical (80%+)",  0.80, 1.01),
    ]
    risk_buckets = []
    for label, lo, hi in buckets:
        mask = (current["churn_probability"] >= lo) & (current["churn_probability"] < hi)
        n = int(mask.sum())
        risk_buckets.append({
            "bucket": label,
            "count": n,
            "pct": round(n / n_customers * 100, 2) if n_customers else 0.0,
        })

    # ── Feature importance ──────────────────────────────────────────────────
    coefs = model.coef_[0]
    feature_importance = sorted(
        [
            {"feature": f, "coefficient": round(float(c), 4),
             "abs_importance": round(float(abs(c)), 4)}
            for f, c in zip(feature_cols, coefs)
        ],
        key=lambda r: r["abs_importance"], reverse=True,
    )

    # ── Top at-risk customers ───────────────────────────────────────────────
    top = current.nlargest(TOP_N_AT_RISK, "churn_probability")
    top_at_risk = [
        {
            "customer_id":      str(r["customer_id"]),
            "churn_probability": float(r["churn_probability"]),
            "recency_days":     int(r["recency_days"]),
            "frequency":        int(r["frequency"]),
            "monetary":         round(float(r["monetary"]), 2),
            "lifespan_days":    int(r["lifespan_days"]),
        }
        for r in top.to_dict("records")
    ]

    ml_summary = {
        "n_customers": n_customers,
        "snapshot_date": snapshot.date().isoformat(),
        "churn_threshold_days": CHURN_THRESHOLD_DAYS,
        "n_churned_historical": n_churned,
        "churn_rate_historical_pct": round(n_churned / len(train_features) * 100, 2),
        "avg_churn_risk": round(float(current["churn_probability"].mean()), 4),
        "model_accuracy": round(test_acc, 4) if test_acc is not None else None,
        "model_method": "Logistic Regression (class_weight=balanced)",
    }
    return {
        **_build_contract(ml_summary, risk_buckets, top_at_risk),
        "summary": ml_summary,
        "risk_buckets": risk_buckets,
        "feature_importance": feature_importance,
        "top_at_risk": top_at_risk,
        "warning": None,
    }


def _heuristic_score(df: pd.DataFrame, snapshot: pd.Timestamp,
                     amount_col: str, n_churned_train: int) -> dict[str, Any]:
    """Recency-based survival heuristic.

    P(churn) = 1 - exp(-max(recency - grace, 0) / scale)

    With grace=30 and scale=90 days:
      recency=0    → 0%   churn risk
      recency=30   → 0%   (still in grace window)
      recency=60   → 28%
      recency=90   → 49%
      recency=180  → 81%
      recency=365  → 98%

    Honest framing: not a learned model, just decay. Output shape matches the
    ML branch so the dashboard doesn't care which produced it.
    """
    grace = 30.0
    scale = 90.0

    cur = _per_customer_features(df, snapshot, amount_col)
    n_customers = int(len(cur))

    decay = np.clip(cur["recency_days"].astype(float) - grace, a_min=0, a_max=None)
    cur["churn_probability"] = np.round(1.0 - np.exp(-decay / scale), 4)

    # Bucket distribution
    buckets_def = [
        ("low (0-20%)",      0.00, 0.20),
        ("medium (20-50%)",  0.20, 0.50),
        ("high (50-80%)",    0.50, 0.80),
        ("critical (80%+)",  0.80, 1.01),
    ]
    risk_buckets = []
    for label, lo, hi in buckets_def:
        mask = (cur["churn_probability"] >= lo) & (cur["churn_probability"] < hi)
        n = int(mask.sum())
        risk_buckets.append({
            "bucket": label,
            "count": n,
            "pct": round(n / n_customers * 100, 2) if n_customers else 0.0,
        })

    # Feature "importance" — only recency drives the heuristic, document that.
    feature_importance = [
        {"feature": "recency_days", "coefficient": 1.0,  "abs_importance": 1.0},
        {"feature": "frequency",    "coefficient": 0.0,  "abs_importance": 0.0},
        {"feature": "monetary",     "coefficient": 0.0,  "abs_importance": 0.0},
    ]

    top = cur.nlargest(TOP_N_AT_RISK, "churn_probability")
    top_at_risk = [
        {
            "customer_id":      str(r["customer_id"]),
            "churn_probability": float(r["churn_probability"]),
            "recency_days":     int(r["recency_days"]),
            "frequency":        int(r["frequency"]),
            "monetary":         round(float(r["monetary"]), 2),
            "lifespan_days":    int(r["lifespan_days"]),
        }
        for r in top.to_dict("records")
    ]

    heur_summary = {
        "n_customers": n_customers,
        "snapshot_date": snapshot.date().isoformat(),
        "churn_threshold_days": CHURN_THRESHOLD_DAYS,
        "n_churned_historical": n_churned_train,
        "churn_rate_historical_pct": 0.0,  # not meaningful here
        "avg_churn_risk": round(float(cur["churn_probability"].mean()), 4),
        "model_accuracy": None,
        "model_method": (
            "Recency heuristic: 1 - exp(-(recency-30)/90)  "
            "(no ML — training labels were degenerate)"
        ),
    }
    return {
        **_build_contract(heur_summary, risk_buckets, top_at_risk),
        "summary": heur_summary,
        "risk_buckets": risk_buckets,
        "feature_importance": feature_importance,
        "top_at_risk": top_at_risk,
        "warning": (
            "Logistic Regression couldn't train (degenerate labels — dataset is "
            "one-time-buyer heavy). Showing recency-based churn decay instead."
        ),
    }


def _build_contract(summary: dict, risk_buckets: list, top_at_risk: list,
                     warning: str | None = None) -> dict[str, Any]:
    """Build question/headline/bullets/actions from churn output.

    Called from both the ML branch and the heuristic branch so the dashboard
    sees the same contract no matter which model produced the numbers.
    """
    n_critical = next(
        (b["count"] for b in risk_buckets if b["bucket"].startswith("critical")),
        0,
    )
    n_high = next(
        (b["count"] for b in risk_buckets if b["bucket"].startswith("high")),
        0,
    )
    avg_risk_pct = float(summary.get("avg_churn_risk") or 0.0) * 100
    n_customers = int(summary.get("n_customers") or 0)

    headline = build_headline(
        value=n_critical + n_high,
        label="customers at risk of churning",
        trend_pct=None,
        period="Current snapshot",
    )

    bullets: list[str] = []
    # 1 — Risk headline
    if n_critical >= 1:
        bullets.append(
            f"{fmt_int(n_critical)} customers are 80%+ likely to churn — "
            f"every day you wait, the recovery odds drop."
        )
    elif n_high >= 1:
        bullets.append(
            f"{fmt_int(n_high)} customers in the high-risk band (50–80%) — "
            f"warm them up with a personalised offer this week."
        )
    elif n_customers > 0:
        bullets.append(
            f"Healthy: average churn risk is just {avg_risk_pct:.1f}% across "
            f"{fmt_int(n_customers)} customers — strong retention."
        )
    else:
        bullets.append(
            "Not enough customer data yet — churn model needs at least "
            "50 customers with multi-month history."
        )

    # 2 — Top at-risk callout
    if top_at_risk:
        worst = top_at_risk[0]
        recency = int(worst.get("recency_days") or 0)
        bullets.append(
            f"Most at risk: customer {str(worst.get('customer_id'))[:12]} — "
            f"silent for {recency} days, {worst.get('frequency')} prior orders."
        )
    else:
        bullets.append(
            "Once enough history accrues, this card surfaces the 25 most "
            "at-risk customers with personal recency, frequency, monetary."
        )

    # 3 — Action framing
    if n_critical + n_high >= 5:
        bullets.append(
            "Send a win-back email this week — for high-LTV customers, even "
            "a $10 incentive often beats the cost of acquiring a new buyer."
        )
    elif avg_risk_pct > 20:
        bullets.append(
            "Churn risk is creeping up — review your last 3 months of "
            "post-purchase emails: are you re-engaging at 30/60/90 days?"
        )
    else:
        bullets.append(
            "Set up a 60-day silent-customer trigger so this card alerts "
            "you the moment a VIP goes quiet."
        )

    actions = [
        action("View at-risk list", kind="primary",
               deeplink="/dashboard/customers?filter=at-risk", icon="arrow"),
    ]
    if n_critical + n_high >= 3:
        actions.append(action(
            "Launch win-back campaign", kind="warning",
            deeplink="/dashboard/segmentation?segment=at-risk&action=export",
            icon="arrow",
        ))
    actions.append(action(
        "Export at-risk CSV", kind="secondary", deeplink=None, icon="download",
    ))

    return build_payload(
        question=QUESTION,
        headline=headline,
        fallback_bullets=bullets,
        suggested_actions=actions[:3],
    )


def _empty(warning: str) -> dict[str, Any]:
    empty_summary = {
        "n_customers": 0, "snapshot_date": None,
        "churn_threshold_days": CHURN_THRESHOLD_DAYS,
        "n_churned_historical": 0, "churn_rate_historical_pct": 0.0,
        "avg_churn_risk": 0.0, "model_accuracy": None,
        "model_method": "Logistic Regression (class_weight=balanced)",
    }
    return {
        **_build_contract(empty_summary, [], [], warning=warning),
        "summary": empty_summary,
        "risk_buckets": [],
        "feature_importance": [],
        "top_at_risk": [],
        "warning": warning,
    }
