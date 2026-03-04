"""Placeholder — Step 13 (Phase 3): Groq LLM natural language insight generation."""

from celery_app import celery_app


@celery_app.task(bind=True, name="tasks.insights.run_insights")
def run_insights(self, job_id: str):
    """Send synthesised summary to Groq LLaMA 3 and store 3 bullet insights."""
    # TODO: Implement in Phase 3 (Step 13)
    raise NotImplementedError("Insights task not yet implemented.")
