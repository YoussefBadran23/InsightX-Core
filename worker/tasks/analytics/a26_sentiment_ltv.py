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
from ._contract import action, build_headline, build_payload, fmt_int, fmt_money


QUESTION = "Are my happy customers actually spending more than my unhappy ones?"


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

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    n_customers = int(len(per_cust))
    headline = build_headline(
        value=lift_pct if lift_pct is not None else round(pearson * 100, 1),
        label=("LTV lift · happy vs unhappy customers"
               if lift_pct is not None
               else "sentiment-LTV correlation"),
        period=f"{fmt_int(n_customers)} customers with comments",
    )

    bullets: list[str] = []
    # 1 — Correlation framing
    if lift_pct is not None:
        if lift_pct >= 30:
            bullets.append(
                f"Happy customers spend {lift_pct:.0f}% more than unhappy ones "
                f"({fmt_money(pos_ltv)} vs {fmt_money(neg_ltv)} avg LTV). "
                f"Service is a revenue lever."
            )
        elif lift_pct <= -10:
            bullets.append(
                f"Unhappy customers actually spend {abs(lift_pct):.0f}% MORE — "
                f"big spenders complain more (or vice versa). Investigate."
            )
        else:
            bullets.append(
                f"Happy vs unhappy spend almost the same ({lift_pct:+.0f}% lift) — "
                f"sentiment doesn't strongly predict basket size here."
            )
    else:
        bullets.append(
            f"Correlation analysis: {_interpret_correlation(pearson)} "
            f"(Pearson r = {pearson:+.2f})."
        )

    # 2 — Happy-high-value count
    n_happy_high = len([r for r in happy_top.to_dict("records") if r.get("avg_sentiment", 0) > 0])
    n_angry_high = len([r for r in angry_top.to_dict("records") if r.get("avg_sentiment", 0) < 0])

    if n_angry_high > 0:
        bullets.append(
            f"{fmt_int(n_angry_high)} high-value customers wrote negative comments — "
            f"reach out personally; their unhappiness is your most expensive churn risk."
        )
    elif n_happy_high > 0:
        bullets.append(
            f"{fmt_int(n_happy_high)} of your top spenders are happy — "
            f"ask them for testimonials and referrals while sentiment is hot."
        )

    # 3 — Action recommendation
    if pearson > 0.3:
        bullets.append(
            "Strong link between mood and money — invest in CX: faster shipping, "
            "honest descriptions, and proactive support multiply revenue."
        )
    elif pearson < -0.1:
        bullets.append(
            "Negative correlation is unusual — likely a measurement artefact "
            "(big spenders complain more because they care more). Inspect manually."
        )
    else:
        bullets.append(
            "Sentiment is weak signal here — focus retention spend on RFM segments "
            "(A02) instead of comment-driven outreach."
        )

    actions = [
        action("View by sentiment", kind="primary",
               deeplink="/dashboard/analytics?focus=A26", icon="arrow"),
    ]
    if n_angry_high > 0:
        actions.append(action(
            "Reach out to unhappy whales", kind="danger",
            deeplink="/dashboard/customers?filter=angry-high-value", icon="arrow",
        ))
    actions.append(action(
        "Export sentiment×LTV report", kind="secondary", deeplink=None, icon="download",
    ))

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions[:3],
        ),
        "summary": {
            "n_customers":         n_customers,
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
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="happy vs unhappy LTV lift",
                                    period="no data"),
            fallback_bullets=[
                "Need at least 20 customers with comment_text to correlate "
                "sentiment with lifetime value.",
                "Once you have reviews or feedback per customer, this card tells "
                "you whether happy customers spend more (and by how much).",
                "Tip: even 1-5 star ratings or NPS surveys feed this metric — "
                "it's the cleanest measure of how CX moves revenue.",
            ],
            suggested_actions=[
                action("Add customer comments", kind="primary",
                       deeplink="/dashboard/settings/data-sources", icon="arrow"),
            ],
        ),
        "summary": {
            "n_customers": 0, "n_comments_total": 0,
            "pearson_correlation": 0.0, "interpretation": "no data",
            "lift_pos_vs_neg_pct": None,
            "avg_ltv_positive": None, "avg_ltv_negative": None,
        },
        "by_sentiment": [], "happy_high_value": [], "angry_high_value": [],
        "warning": warning,
    }
