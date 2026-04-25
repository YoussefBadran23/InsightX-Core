"""A18 — Sentiment Analysis (LLM-based).

Classifies order comments as POSITIVE / NEGATIVE / NEUTRAL using
the OpenAI-compatible API (Groq, LM Studio, or Ollama).
Updates orders.sentiment_label and orders.sentiment_score.
"""

import os
import logging
import pandas as pd
from sqlalchemy import text
from ._base import analytics_task, has_col

logger = logging.getLogger(__name__)

_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://host.docker.internal:1234/v1")
_LLM_KEY = os.getenv("LOCAL_LLM_API_KEY", "lm-studio")
_GROQ_KEY = os.getenv("GROQ_API_KEY", "")


def _get_client():
    """Return an OpenAI-compatible client, preferring Groq if key is set."""
    from openai import OpenAI

    if _GROQ_KEY:
        return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=_GROQ_KEY, timeout=30)
    return OpenAI(base_url=_LLM_URL, api_key=_LLM_KEY, timeout=30)


def _classify_batch(client, comments: list[str]) -> list[dict]:
    """Send a batch of comments to LLM for sentiment classification."""
    if not comments:
        return []

    numbered = "\n".join(f"{i+1}. {c[:200]}" for i, c in enumerate(comments))
    prompt = (
        f"Classify each comment as POSITIVE, NEGATIVE, or NEUTRAL. "
        f"Reply with ONLY one word per line (the sentiment label).\n\n{numbered}"
    )

    try:
        model = "llama-3.3-70b-versatile" if _GROQ_KEY else "local-model"
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a sentiment classifier. Reply with one label per line: POSITIVE, NEGATIVE, or NEUTRAL."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=len(comments) * 15,
        )
        lines = resp.choices[0].message.content.strip().split("\n")
    except Exception as e:
        logger.warning("LLM sentiment call failed: %s — falling back to NEUTRAL", e)
        return [{"label": "NEUTRAL", "score": 0.5} for _ in comments]

    results = []
    for i, line in enumerate(lines):
        cleaned = line.strip().upper().replace(".", "")
        # Extract just the sentiment word
        for word in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:
            if word in cleaned:
                cleaned = word
                break
        else:
            cleaned = "NEUTRAL"

        score_map = {"POSITIVE": 0.85, "NEGATIVE": 0.15, "NEUTRAL": 0.50}
        results.append({"label": cleaned, "score": score_map.get(cleaned, 0.5)})

    # Pad if LLM returned fewer lines
    while len(results) < len(comments):
        results.append({"label": "NEUTRAL", "score": 0.5})

    return results


@analytics_task("A18_sentiment_analysis", "sentiment")
def run_sentiment_analysis(df, session, job_id):
    if not has_col(df, "comment_text"):
        return {
            "distribution": [],
            "summary": "No comment_text column found — skipping sentiment analysis",
            "total_analyzed": 0,
        }

    comments_df = df[df["comment_text"].notna() & (df["comment_text"].str.strip() != "")].copy()

    if len(comments_df) == 0:
        return {
            "distribution": [],
            "summary": "No non-empty comments found",
            "total_analyzed": 0,
        }

    client = _get_client()

    # Process in batches of 20
    batch_size = 20
    all_results = []
    for start in range(0, len(comments_df), batch_size):
        batch = comments_df.iloc[start:start + batch_size]
        batch_comments = batch["comment_text"].tolist()
        batch_results = _classify_batch(client, batch_comments)
        all_results.extend(batch_results)

    comments_df["sentiment_label"] = [r["label"] for r in all_results[:len(comments_df)]]
    comments_df["sentiment_score"] = [r["score"] for r in all_results[:len(comments_df)]]

    # Update orders table
    if has_col(df, "id"):
        for _, row in comments_df.iterrows():
            order_ext_id = str(row.get("id", ""))
            if order_ext_id:
                session.execute(
                    text("""
                        UPDATE orders
                        SET sentiment_label = :label, sentiment_score = :score, updated_at = NOW()
                        WHERE external_id = :oid
                    """),
                    {"label": row["sentiment_label"], "score": float(row["sentiment_score"]), "oid": order_ext_id},
                )
        session.commit()

    # Distribution
    dist = comments_df["sentiment_label"].value_counts().reset_index()
    dist.columns = ["label", "count"]
    dist["pct"] = (dist["count"] / len(comments_df) * 100).round(2)

    # Sample comments per sentiment
    samples = {}
    for label in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:
        subset = comments_df[comments_df["sentiment_label"] == label]
        samples[label.lower()] = subset["comment_text"].head(5).tolist()

    return {
        "distribution": dist.to_dict("records"),
        "samples": samples,
        "total_analyzed": len(comments_df),
        "total_orders": len(df),
    }
