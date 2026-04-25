"""Step 13 (Phase 3): Local LLM natural language insight generation."""

import os
import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from openai import OpenAI

from celery_app import celery_app
from app.models.insight import Insight
from app.models.analysis_results_cache import AnalysisResultsCache

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))


@celery_app.task(bind=True, name="tasks.insights.run_insights")
def run_insights(self, job_id: str):
    """Send synthesised summary to Local LLM (LM Studio/Ollama) and store 3 bullet insights."""
    logger.info("Starting insights generation for job %s", job_id)

    local_url = os.getenv("LOCAL_LLM_URL", "http://host.docker.internal:1234/v1")
    api_key = os.getenv("LOCAL_LLM_API_KEY", "lm-studio")

    db = SessionLocal()
    try:
        # Query the most recent analytics result for this job to use as context
        cache = (
            db.query(AnalysisResultsCache)
            .filter(AnalysisResultsCache.upload_job_id == job_id)
            .order_by(AnalysisResultsCache.computed_at.desc())
            .first()
        )
        if not cache:
            logger.error("No analysis results found for job %s", job_id)
            return {"status": "error", "message": f"Analysis results missing for {job_id}"}

        system_prompt = (
            "You are an expert data analyst. Based on the provided data, generate EXACTLY 3 short, "
            "actionable business insights formatted as plain text bullet points. "
            "Do not include any introductory or concluding text."
        )
        user_prompt = f"Data Summary: {str(cache.result_json)[:2000]}"

        logger.info("Calling Local LLM for job %s (timeout=%ds)…", job_id, _LLM_TIMEOUT_SECONDS)
        client = OpenAI(base_url=local_url, api_key=api_key, timeout=_LLM_TIMEOUT_SECONDS)

        response = client.chat.completions.create(
            model="local-model",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=250,
        )

        llm_text = response.choices[0].message.content.strip()
        bullets = [
            b.strip().lstrip("-").lstrip("*").strip()
            for b in llm_text.split("\n")
            if b.strip()
        ][:3]

        while len(bullets) < 3:
            bullets.append("[Insight unavailable — insufficient data]")

        for i, b_text in enumerate(bullets, start=1):
            db.add(Insight(
                job_id=job_id,
                source_type=cache.analysis_type,
                bullet_index=i,
                bullet_text=b_text,
            ))

        db.commit()
        logger.info("Saved 3 insights for job %s", job_id)
        return {"status": "success"}

    except Exception as e:
        logger.error("Failed to generate insights for job %s: %s", job_id, e)
        # NOTE: Insights are best-effort — do NOT mutate the job status here.
        # The pipeline (finalize task) has already set the job to 'completed'.
        # Overriding it would incorrectly show the upload as failed in the UI.
        raise self.retry(exc=e, countdown=60, max_retries=3)
    finally:
        db.close()
