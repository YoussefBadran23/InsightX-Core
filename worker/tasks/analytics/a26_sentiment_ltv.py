"""A26 — Sentiment × LTV Correlation.

Joins per-customer sentiment (from comment_text) with per-customer lifetime
value, then reports the correlation. Surfaces the lift in spend between
positive-sentiment and negative-sentiment customers.

Required columns:  comment_text, customer_id, total_amount
Optional:          order_date, net_amount
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from ._base import coerce_date, coerce_numeric, has_col, register


_ARABIC_RE = re.compile(r"[؀-ۿ]")


def _score_text(text: str) -> float:
    """Reuse the A18 lexicon at low cost — duplicated here to avoid a hard
    cross-module import dependency. Coarse but enough to bucket customers."""
    from . import a18_sentiment_analysis as a18
    if not isinstance(text, str) or not text.strip():
        return 0.0
    if _ARABIC_RE.search(text):
        return a18._arabic_score(text)
    # English: rule-based heuristic — count positive/negative cue words.
    t = text.lower()
    pos_hits = sum(1 for w in ("good", "great", "love", "perfect", "excellent",
                                "amazing", "best", "fast", "thank", "happy",
                                "awesome", "recommend", "wonderful") if w in t)
    neg_hits = sum(1 for w in ("bad", "terrible", "worst", "broken", "slow",
                                "never", "scam", "refund", "missing", "damaged",
                                "horrible", "awful", "wrong", "late") if w in t)
    if pos_hits == 0 and neg_hits == 0:
        return 0.0
    return max(-1.0, min(1.0, (pos_hits - neg_hits) / max(pos_hits + neg_hits, 1)))


@register(
    key="A26_sentiment_ltv",
    analysis_type="customer",
    required_cols=["comment_text", "customer_id", "total_amount"],
    optional_cols=["order_date", "net_amount"],
    description="Pearson correlation between per-customer sentiment and LTV.",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df["total_amount"] = coerce_numeric(df["total_amount"])
    if has_col(df, "net_amount"):
        df["net_amount"] = coerce_numeric(df["net_amount"])
    amount_col = "net_amount" if has_col(df, "net_amount") else "total_amount"
    df = df.dropna(subset=["customer_id", amount_col, "comment_text"])
    df["customer_id"] = df["customer_id"].astype(str)
    df["comment_text"] = df["comment_text"].astype(str)
    df = df[df["comment_text"].str.strip() != ""]
    df = df[df[amount_col] >= 0]

    if df.empty or df["customer_id"].nunique() < 20:
        return _empty(
            f"only {df['customer_id'].nunique()} customers with comments — need ≥20"
        )

    # ── Score each comment, average per customer ────────────────────────────
    df["_score"] = df["comment_text"].apply(_score_text)
    per_cust = df.groupby("customer_id").agg(
        avg_sentiment=("_score", "mean"),
        n_comments=("_score", "count"),
        lifetime_value=(amount_col, "sum"),
        n_orders=("_score", "size"),
    ).reset_index()

    per_cust["sentiment_label"] = pd.cut(
        per_cust["avg_sentiment"],
        bins=[-1.01, -0.1, 0.1, 1.01],
        labels=["negative", "neutral", "positive"],
    ).astype(str)

    # Pearson correlation
    if per_cust["avg_sentiment"].std() == 0 or per_cust["lifetime_value"].std() == 0:
        pearson = 0.0
    else:
        pearson = float(np.corrcoef(per_cust["avg_sentiment"], per_cust["lifetime_value"])[0, 1])

    # Per-bucket aggregates
    bucket_stats = []
    for label in ("positive", "neutral", "negative"):
        sub = per_cust[per_cust["sentiment_label"] == label]
        if sub.empty:
            continue
        bucket_stats.append({
            "sentiment":      label,
            "customers":      int(len(sub)),
            "pct":            round(len(sub) / len(per_cust) * 100, 2),
            "avg_ltv":        round(float(sub["lifetime_value"].mean()), 2),
            "median_ltv":     round(float(sub["lifetime_value"].median()), 2),
            "total_revenue":  round(float(sub["lifetime_value"].sum()), 2),
            "avg_orders":     round(float(sub["n_orders"].mean()), 2),
        })

    # Lift: positive vs negative average LTV
    pos_ltv = next((b["avg_ltv"] for b in bucket_stats if b["sentiment"] == "positive"), None)
    neg_ltv = next((b["avg_ltv"] for b in bucket_stats if b["sentiment"] == "negative"), None)
    lift_pct = None
    if pos_ltv is not None and neg_ltv is not None and neg_ltv > 0:
        lift_pct = round((pos_ltv - neg_ltv) / neg_ltv * 100, 2)

    # Top movers — happiest and angriest big spenders
    happy_top = per_cust.nlargest(10, "lifetime_value")
    happy_top = happy_top[happy_top["avg_sentiment"] > 0]
    angry_top = per_cust.nlargest(10, "lifetime_value")
    angry_top = angry_top[angry_top["avg_sentiment"] < 0]

    def _to_record(r: pd.Series) -> dict[str, Any]:
        return {
            "customer_id":    str(r["customer_id"]),
            "avg_sentiment":  round(float(r["avg_sentiment"]), 3),
            "n_comments":     int(r["n_comments"]),
            "lifetime_value": round(float(r["lifetime_value"]), 2),
            "n_orders":       int(r["n_orders"]),
        }

    return {
        "summary": {
            "n_customers":         int(len(per_cust)),
            "n_comments_total":    int(len(df)),
            "pearson_correlation": round(pearson, 4),
            "interpretation":      _interpret_correlation(pearson),
            "lift_pos_vs_neg_pct": lift_pct,
            "avg_ltv_positive":    pos_ltv,
            "avg_ltv_negative":    neg_ltv,
        },
        "by_sentiment":  bucket_stats,
        "happy_high_value":  [_to_record(r) for r in happy_top.to_dict("records")][:5],
        "angry_high_value":  [_to_record(r) for r in angry_top.to_dict("records")][:5],
        "warning": None,
    }


def _interpret_correlation(r: float) -> str:
    a = abs(r)
    if a < 0.1:
        return "no relationship — sentiment doesn't predict spend"
    if a < 0.3:
        return f"weak {'positive' if r > 0 else 'negative'} relationship"
    if a < 0.6:
        return f"moderate {'positive' if r > 0 else 'negative'} relationship"
    return f"strong {'positive' if r > 0 else 'negative'} relationship"


def _empty(warning: str) -> dict[str, Any]:
    return {
        "summary": {
            "n_customers": 0, "n_comments_total": 0,
            "pearson_correlation": 0.0, "interpretation": "no data",
            "lift_pos_vs_neg_pct": None,
            "avg_ltv_positive": None, "avg_ltv_negative": None,
        },
        "by_sentiment": [], "happy_high_value": [], "angry_high_value": [],
        "warning": warning,
    }
