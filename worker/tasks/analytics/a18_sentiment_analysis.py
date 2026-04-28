"""A18 — Sentiment Analysis (LLM-based) (Optimized & Complete)."""
import os
import pandas as pd
from sqlalchemy import text
from ._base import analytics_task, has_col
from openai import OpenAI

COLS = ["id", "comment_text"]
_GROQ_KEY = os.getenv("GROQ_API_KEY", "")

@analytics_task("A18_sentiment_analysis", "sentiment", required_cols=COLS)
def run_sentiment_analysis(df, session, job_id):
    comments_df = df[df["comment_text"].notna() & (df["comment_text"].str.strip() != "")].copy()
    if comments_df.empty: return {"summary": "No comments found", "total_analyzed": 0}

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1" if _GROQ_KEY else os.getenv("LOCAL_LLM_URL", "http://host.docker.internal:1234/v1"), 
        api_key=_GROQ_KEY or "local",
        timeout=30
    )

    all_results = []
    # Process in batches of 20 to reduce API round-trips
    for i in range(0, len(comments_df), 20):
        batch = comments_df.iloc[i:i+20]["comment_text"].tolist()
        prompt = "Classify each comment as POSITIVE, NEGATIVE, or NEUTRAL. Reply with ONLY one word per line:\n" + "\n".join(batch)
        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile" if _GROQ_KEY else "local-model",
                messages=[{"role": "system", "content": "You are a sentiment classifier."}, {"role": "user", "content": prompt}],
                temperature=0
            )
            labels = [line.strip().upper() for line in res.choices[0].message.content.split("\n") if line.strip()]
            for label in labels[:len(batch)]:
                clean_label = "POSITIVE" if "POSITIVE" in label else "NEGATIVE" if "NEGATIVE" in label else "NEUTRAL"
                all_results.append(clean_label)
        except:
            all_results.extend(["NEUTRAL"] * len(batch))

    comments_df["sentiment_label"] = all_results[:len(comments_df)]
    score_map = {"POSITIVE": 0.85, "NEGATIVE": 0.15, "NEUTRAL": 0.5}
    comments_df["sentiment_score"] = comments_df["sentiment_label"].map(score_map).fillna(0.5)

    # PERFORMANCE WIN: Batch Update Database
    updates = [{"l": r.sentiment_label, "s": float(r.sentiment_score), "oid": str(r.id)} for r in comments_df.itertuples()]
    if updates:
        session.execute(text("UPDATE orders SET sentiment_label = :l, sentiment_score = :s, updated_at = NOW() WHERE external_id = :oid"), updates)
        session.commit()

    return {
        "distribution": comments_df["sentiment_label"].value_counts(normalize=True).mul(100).round(2).to_dict(),
        "total_analyzed": len(comments_df),
        "samples": {l.lower(): comments_df[comments_df.sentiment_label==l].comment_text.head(3).tolist() for l in ["POSITIVE", "NEGATIVE", "NEUTRAL"]}
    }