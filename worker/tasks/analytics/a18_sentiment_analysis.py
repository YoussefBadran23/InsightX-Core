"""A18 — Sentiment Analysis on Comment Text.

Classifies each `comment_text` row as positive / negative / neutral and
aggregates the distribution. Engine selection is layered so the module
works in any environment:

1. **transformers BERT** (preferred): multilingual, high quality. Used when
   `transformers` + `torch` + a sentiment model are available.
2. **VADER**: rule-based lexicon for English. Pure-Python, fast, no GPU.
3. **Arabic lexicon**: small built-in positive/negative word list with
   negation handling. Coarse but better than nothing for Arabic comments
   when transformers isn't available.

Each comment is routed to the right engine by simple Unicode-range language
detection — Arabic-script (U+0600–U+06FF) goes to the Arabic path; otherwise
the row tries BERT, then VADER.

Output framing
--------------
- Distribution: positive / neutral / negative counts and percentages
- Score histogram: sentiment in 5 buckets (very negative … very positive)
- Per-product / per-category aggregates if those columns exist
- Top positive + top negative comments for quick review
- Engine attribution per row in `_engine_counts`

Required columns:  comment_text
Optional columns:  product_id, product_name, category, customer_id,
                   total_amount, order_date, rating

Output schema::

    {
      "summary": {
        "n_comments":          int,
        "n_analyzed":          int,
        "positive_pct":        float,
        "neutral_pct":         float,
        "negative_pct":        float,
        "avg_score":           float,           # -1 to 1
        "engines_used":        {"transformers": int, "vader": int, "arabic_lexicon": int},
        "primary_engine":      str
      },
      "score_distribution": [
        {"bucket": "very_negative", "count": int, "pct": float}
      ],
      "by_category":   [...] | null,
      "by_product":    [...] | null,
      "top_positive":  [{"text": str, "score": float, "product_id": str|null}],
      "top_negative":  [{"text": str, "score": float, "product_id": str|null}],
      "warning": str | null
    }
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import pandas as pd

from ._base import has_col, register
from ._contract import action, build_headline, build_payload, fmt_int


QUESTION = "Are my customers happy or upset about something?"

logging.getLogger("transformers").setLevel(logging.WARNING)


MAX_COMMENTS = 5000        # cap to bound runtime; sample if more
SCORE_BUCKETS = [
    (-1.001, -0.5,  "very_negative"),
    (-0.5,    -0.1, "negative"),
    (-0.1,     0.1, "neutral"),
    (0.1,      0.5, "positive"),
    (0.5,      1.001, "very_positive"),
]
TOP_PER_BUCKET = 10

# Arabic Unicode block — quick language detector. We don't need a real langID
# library; presence of any character in this range routes the row to the
# Arabic engine.
_ARABIC_RE = re.compile(r"[؀-ۿ]")


# ── Arabic lexicon (small, hand-curated) ────────────────────────────────────
# Coarse but surprisingly effective for review-style text. If a future user
# wants higher quality, install transformers and a multilingual model.
_AR_POSITIVE = {
    "ممتاز", "ممتازة", "ممتازه", "رائع", "رائعة", "رائعه", "جيد", "جيدة", "جيده",
    "جميل", "جميلة", "حلو", "حلوة", "خرافي", "خرافية", "استثنائي", "استثنائية",
    "افضل", "أفضل", "احسن", "أحسن", "اجمل", "أجمل", "نظيف", "نظيفة", "سريع",
    "مريح", "مميز", "مميزة", "اوصي", "أوصي", "انصح", "أنصح", "احب", "أحب",
    "احببت", "أحببت", "اعجبني", "أعجبني", "عجبني", "سعيد", "شكرا", "شكراً",
    "محترم", "ذوق", "راقي", "مذهل", "مدهش", "روعة", "هايل", "ولا اروع",
    "ولا أروع", "تمام", "زين", "ولا أحلى", "ولا احلى", "لذيذ", "لذيذة",
}
_AR_NEGATIVE = {
    "سيء", "سيئ", "سيئة", "سيئه", "فاشل", "فاشلة", "رديء", "رديئة",
    "بشع", "بشعة", "مزعج", "مزعجة", "بطيء", "بطيئة", "غالي", "غالية",
    "مشكلة", "مشاكل", "خطأ", "اخطاء", "أخطاء", "مكسور", "كسر", "خراب",
    "مخيب", "مخيبة", "تعيس", "تعيسة", "مقرف", "مقرفة", "زبالة", "نصب",
    "كذب", "احتيال", "سرقة", "ضعيف", "ضعيفة", "هزيل", "ندمت",
    "خربان", "خايس", "خايسة", "تافه", "تافهة", "غريب", "كارثة", "ما يصلح",
    "لا يصلح", "ما ينفع", "خراب", "خرابة",
}
_AR_NEGATIONS = {"لا", "لم", "لن", "ما", "مش", "مو", "ليس", "ليست", "غير"}
_AR_INTENSIFIERS = {"جدا", "جداً", "كثير", "كتير", "اوي", "أوي"}


def _normalize_arabic(text: str) -> str:
    """Strip diacritics, normalize alef forms — improves lexicon match rate."""
    text = re.sub(r"[ً-ْ]", "", text)  # tashkeel
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه")  # taa marbuta → haa
    text = text.replace("ى", "ي")  # alef maksura → ya
    return text.lower()


def _arabic_score(text: str) -> float:
    """Lexicon + simple negation. Returns score in [-1, 1]."""
    if not isinstance(text, str) or not text.strip():
        return 0.0
    norm = _normalize_arabic(text)
    tokens = re.findall(r"[؀-ۿ]+", norm)
    if not tokens:
        return 0.0

    pos_set = {_normalize_arabic(w) for w in _AR_POSITIVE}
    neg_set = {_normalize_arabic(w) for w in _AR_NEGATIVE}
    neg_words = {_normalize_arabic(w) for w in _AR_NEGATIONS}

    score = 0.0
    hits = 0
    prev_negation = False
    for i, tok in enumerate(tokens):
        if tok in neg_words:
            prev_negation = True
            continue
        polarity = 0
        if tok in pos_set:
            polarity = 1
        elif tok in neg_set:
            polarity = -1
        if polarity != 0:
            if prev_negation:
                polarity = -polarity
            score += polarity
            hits += 1
            prev_negation = False
        else:
            # Reset negation if a non-sentiment word intervenes too long.
            if i > 0 and tokens[i - 1] not in neg_words:
                prev_negation = False
    if hits == 0:
        return 0.0
    # Normalize by number of polarity words; cap at [-1, 1].
    raw = score / max(hits, 1)
    return max(-1.0, min(1.0, raw))


def _try_transformers() -> Optional[tuple[str, Any]]:
    try:
        from transformers import pipeline
        # Pick a multilingual sentiment model. The default cache lives in
        # ~/.cache/huggingface so subsequent runs are fast.
        clf = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
            top_k=None,
        )
        return ("transformers (xlm-roberta multilingual)", clf)
    except Exception:
        return None


def _try_vader():
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()
    except Exception:
        return None


def _bucket_score(score: float) -> str:
    for lo, hi, label in SCORE_BUCKETS:
        if lo < score <= hi:
            return label
    return "neutral"


@register(
    key="A18_sentiment_analysis",
    analysis_type="customer",
    required_cols=["comment_text"],
    optional_cols=["product_id", "product_name", "category", "customer_id",
                   "total_amount", "order_date", "rating"],
    description="Sentiment classification on comment_text (BERT / VADER / Arabic lexicon).",
)
def run(df: pd.DataFrame) -> dict[str, Any]:
    df = df.copy()
    df = df.dropna(subset=["comment_text"])
    df["comment_text"] = df["comment_text"].astype(str)
    df = df[df["comment_text"].str.strip() != ""]

    if df.empty:
        return _empty("no non-empty comment_text rows")

    # Sample if too many comments — rare in production but seed CSVs may hit it.
    if len(df) > MAX_COMMENTS:
        df = df.sample(n=MAX_COMMENTS, random_state=42)

    n_total = int(len(df))

    # ── Probe engines ───────────────────────────────────────────────────────
    bert = _try_transformers()
    vader = _try_vader()

    engines_used = {"transformers": 0, "vader": 0, "arabic_lexicon": 0}
    scores: list[float] = []

    # ── Score each comment ──────────────────────────────────────────────────
    if bert is not None:
        bert_label, bert_clf = bert
        # Batch-score everything via transformers.
        try:
            results = bert_clf(df["comment_text"].tolist(), truncation=True, max_length=256)
            for r in results:
                # `top_k=None` returns all labels with scores → pick max-prob.
                if isinstance(r, list):
                    pos_p = next((d["score"] for d in r if d["label"].lower() in ("positive", "pos")), 0.0)
                    neg_p = next((d["score"] for d in r if d["label"].lower() in ("negative", "neg")), 0.0)
                    score = pos_p - neg_p
                else:
                    label = r.get("label", "neutral").lower()
                    p = r.get("score", 0.0)
                    if label in ("positive", "pos"):
                        score = p
                    elif label in ("negative", "neg"):
                        score = -p
                    else:
                        score = 0.0
                scores.append(score)
                engines_used["transformers"] += 1
        except Exception as e:
            # Mid-batch failure — fall through to per-row engines.
            logging.warning(f"A18 transformers batch failed: {type(e).__name__}: {e}")
            scores = []
            engines_used["transformers"] = 0

    if not scores:
        # Per-row routing: Arabic-script → lexicon; otherwise → VADER.
        for text in df["comment_text"].tolist():
            if _ARABIC_RE.search(text):
                scores.append(_arabic_score(text))
                engines_used["arabic_lexicon"] += 1
            elif vader is not None:
                scores.append(vader.polarity_scores(text)["compound"])
                engines_used["vader"] += 1
            else:
                # Last resort — neutral. Nothing in the env can score this.
                scores.append(0.0)

    df = df.assign(_score=scores)
    df["_bucket"] = df["_score"].map(_bucket_score)
    df["_class"] = df["_score"].apply(
        lambda s: "positive" if s > 0.1 else ("negative" if s < -0.1 else "neutral")
    )

    # ── Distribution ────────────────────────────────────────────────────────
    class_counts = df["_class"].value_counts()
    n_pos = int(class_counts.get("positive", 0))
    n_neu = int(class_counts.get("neutral", 0))
    n_neg = int(class_counts.get("negative", 0))
    avg_score = round(float(df["_score"].mean()), 4)

    score_dist = []
    bucket_counts = df["_bucket"].value_counts()
    for _, _, label in SCORE_BUCKETS:
        cnt = int(bucket_counts.get(label, 0))
        score_dist.append({
            "bucket": label,
            "count": cnt,
            "pct": round(cnt / n_total * 100, 2),
        })

    primary = max(engines_used.items(), key=lambda kv: kv[1])[0] if engines_used else "none"
    if engines_used.get("transformers", 0) > 0:
        primary_label = "transformers (xlm-roberta multilingual)"
    elif primary == "vader":
        primary_label = "vader (English lexicon)"
    elif primary == "arabic_lexicon":
        primary_label = "arabic_lexicon (built-in)"
    else:
        primary_label = "none"

    summary = {
        "n_comments": n_total,
        "n_analyzed": n_total,
        "positive_pct": round(n_pos / n_total * 100, 2),
        "neutral_pct": round(n_neu / n_total * 100, 2),
        "negative_pct": round(n_neg / n_total * 100, 2),
        "avg_score": avg_score,
        "engines_used": engines_used,
        "primary_engine": primary_label,
    }

    # ── Per-product / per-category aggregates ───────────────────────────────
    by_category = None
    if has_col(df, "category"):
        sub = df.dropna(subset=["category"]).copy()
        if not sub.empty:
            sub["category"] = sub["category"].astype(str)
            cat_agg = (
                sub.groupby("category")
                   .agg(comments=("_score", "count"),
                        avg_score=("_score", "mean"),
                        positive=("_class", lambda s: int((s == "positive").sum())),
                        negative=("_class", lambda s: int((s == "negative").sum())))
                   .reset_index().sort_values("avg_score", ascending=False)
            )
            cat_agg["positive_pct"] = (cat_agg["positive"] / cat_agg["comments"] * 100).round(2)
            cat_agg["negative_pct"] = (cat_agg["negative"] / cat_agg["comments"] * 100).round(2)
            by_category = [
                {
                    "category": str(r["category"]),
                    "comments": int(r["comments"]),
                    "avg_score": round(float(r["avg_score"]), 3),
                    "positive_pct": float(r["positive_pct"]),
                    "negative_pct": float(r["negative_pct"]),
                }
                for r in cat_agg.head(20).to_dict("records")
            ]

    by_product = None
    if has_col(df, "product_id"):
        sub = df.dropna(subset=["product_id"]).copy()
        sub["product_id"] = sub["product_id"].astype(str)
        prod_agg = (
            sub.groupby("product_id")
               .agg(comments=("_score", "count"),
                    avg_score=("_score", "mean"))
               .reset_index()
        )
        prod_agg = prod_agg[prod_agg["comments"] >= 5]  # noise floor
        if not prod_agg.empty:
            prod_agg = prod_agg.sort_values("avg_score", ascending=False)
            by_product = [
                {"product_id": str(r["product_id"]),
                 "comments": int(r["comments"]),
                 "avg_score": round(float(r["avg_score"]), 3)}
                for r in pd.concat([prod_agg.head(10), prod_agg.tail(10)]).drop_duplicates().to_dict("records")
            ]

    # ── Top positive + top negative comments ────────────────────────────────
    top_pos = df.nlargest(TOP_PER_BUCKET, "_score")
    top_neg = df.nsmallest(TOP_PER_BUCKET, "_score")

    def _to_top_record(r: dict) -> dict[str, Any]:
        return {
            "text": str(r["comment_text"])[:200],
            "score": round(float(r["_score"]), 3),
            "product_id": str(r["product_id"]) if r.get("product_id") and pd.notna(r["product_id"]) else None,
        }

    top_positive = [_to_top_record(r) for r in top_pos.to_dict("records")]
    top_negative = [_to_top_record(r) for r in top_neg.to_dict("records")]

    # ── Decision-Chart v1 contract ─────────────────────────────────────────
    pos_pct = summary["positive_pct"]
    neg_pct = summary["negative_pct"]
    neu_pct = summary["neutral_pct"]
    headline = build_headline(
        value=pos_pct,
        label="positive sentiment",
        trend_pct=None,
        period=f"{fmt_int(n_total)} comments analysed",
    )

    bullets: list[str] = []
    if pos_pct >= 70:
        bullets.append(
            f"Customers love you: {pos_pct:.1f}% positive across "
            f"{fmt_int(n_total)} comments — engineered word-of-mouth fuel."
        )
    elif neg_pct >= 30:
        bullets.append(
            f"Warning: {neg_pct:.1f}% of comments are negative — review the "
            f"top-5 negative quotes today and respond personally."
        )
    elif pos_pct - neg_pct >= 20:
        bullets.append(
            f"Net positive: {pos_pct:.0f}% happy vs {neg_pct:.0f}% unhappy — "
            f"healthy but watch the negative tail."
        )
    else:
        bullets.append(
            f"Mixed signal: {pos_pct:.0f}% positive / {neu_pct:.0f}% neutral / "
            f"{neg_pct:.0f}% negative — investigate root causes."
        )

    worst_cat = None
    if by_category:
        worst_cat = max(by_category, key=lambda r: r.get("negative_pct", 0))
        if worst_cat.get("negative_pct", 0) < 15:
            worst_cat = None
    if worst_cat:
        bullets.append(
            f"Worst category: '{worst_cat['category']}' with "
            f"{worst_cat['negative_pct']:.0f}% negative — investigate this "
            f"category's quality or messaging."
        )
    elif top_negative:
        sample = top_negative[0]["text"][:80]
        bullets.append(
            f"Most negative comment: \"{sample}...\" — read the full list "
            f"to spot patterns (delivery, quality, support?)."
        )
    else:
        bullets.append(
            "Not enough sentiment data for category-level drill-downs — "
            "encourage more post-purchase reviews."
        )

    primary = summary.get("primary_engine", "none")
    if neg_pct >= 20:
        bullets.append(
            "Personally reply to your top-5 negative comments this week — "
            "public response converts critics into evangelists."
        )
    elif "arabic" in primary.lower():
        bullets.append(
            "Arabic NLP is active — Arabic-speaking customers' sentiment is "
            "now visible alongside English. Use it to localise messaging."
        )
    else:
        bullets.append(
            f"Sentiment engine in use: {primary}. Add product_id to comments "
            f"to unlock per-SKU sentiment trends."
        )

    actions = [
        action("Read top negatives", kind="primary",
               deeplink="/dashboard/analytics?focus=A18&filter=negative",
               icon="arrow"),
    ]
    if neg_pct >= 15:
        actions.append(action(
            "Respond to critics", kind="warning",
            deeplink="/dashboard/customers?filter=at-risk", icon="arrow",
        ))
    actions.append(action(
        "Export sentiment CSV", kind="secondary", deeplink=None, icon="download",
    ))

    return {
        **build_payload(
            question=QUESTION,
            headline=headline,
            fallback_bullets=bullets,
            suggested_actions=actions[:3],
        ),
        "summary": summary,
        "score_distribution": score_dist,
        "by_category": by_category,
        "by_product": by_product,
        "top_positive": top_positive,
        "top_negative": top_negative,
        "warning": None,
    }


def _empty(warning: str) -> dict[str, Any]:
    return {
        **build_payload(
            question=QUESTION,
            headline=build_headline(value=0, label="positive sentiment (no data)",
                                    period="no data"),
            fallback_bullets=[
                "No customer comments yet — sentiment requires a "
                "`comment_text` column populated with reviews.",
                "Even 50 short comments unlock multilingual sentiment + "
                "per-category and per-product breakdowns.",
                "Tip: prompt customers post-purchase with a 1-tap rating + "
                "optional comment — best feedback you'll ever get.",
            ],
            suggested_actions=[
                action("Enable review collection", kind="primary",
                       deeplink="/dashboard/settings/data-sources",
                       icon="arrow"),
            ],
        ),
        "summary": {
            "n_comments": 0, "n_analyzed": 0,
            "positive_pct": 0.0, "neutral_pct": 0.0, "negative_pct": 0.0,
            "avg_score": 0.0, "engines_used": {"transformers": 0, "vader": 0, "arabic_lexicon": 0},
            "primary_engine": "none",
        },
        "score_distribution": [],
        "by_category": None, "by_product": None,
        "top_positive": [], "top_negative": [],
        "warning": warning,
    }
