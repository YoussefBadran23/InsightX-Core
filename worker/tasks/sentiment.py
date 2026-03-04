"""Placeholder — Step 12 (Phase 3): Multilingual BERT sentiment analysis."""

from celery_app import celery_app


@celery_app.task(bind=True, name="tasks.sentiment.run_sentiment")
def run_sentiment(self, job_id: str):
    """Classify order comments as POSITIVE / NEGATIVE / NEUTRAL."""
    # TODO: Implement in Phase 3 (Step 12)
    raise NotImplementedError("Sentiment task not yet implemented.")
