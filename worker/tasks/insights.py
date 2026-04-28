"""Stage 8 — AI Insight Generation (Optimized & Complete)."""
import os
import logging
import json
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from openai import OpenAI
from celery_app import celery_app

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

@celery_app.task(bind=True, name="tasks.insights.run_insights")
def run_insights(self, job_id: str):
    """
    Synthesizes analytics cache results into 3 natural language business insights.
    Uses Local LLM or Groq based on environment configuration.
    """
    logger.info(f"Generating AI insights for job {job_id}")
    db = SessionLocal()
    
    try:
        # 1. Fetch the latest results from the cache to provide context for the LLM
        cache_data = db.execute(text("""
            SELECT analysis_type, result_json 
            FROM analysis_results_cache 
            WHERE upload_job_id = :jid 
            ORDER BY computed_at DESC LIMIT 3
        """), {"jid": job_id}).fetchall()

        if not cache_data:
            logger.warning(f"No cache found for {job_id}. Skipping insights.")
            return {"status": "skipped", "reason": "no_data"}

        # Build context string for the prompt
        context = "\n".join([f"[{row[0]}]: {json.dumps(row[1])[:500]}" for row in cache_data])

        # 2. Configure LLM Client
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("LOCAL_LLM_API_KEY", "lm-studio")
        base_url = "https://api.groq.com/openai/v1" if os.getenv("GROQ_API_KEY") else os.getenv("LOCAL_LLM_URL", "http://host.docker.internal:1234/v1")
        
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=45)

        # 3. Generate Insights
        system_msg = (
            "You are a Senior E-commerce Strategist. Based on the raw JSON data, "
            "provide EXACTLY 3 powerful, actionable business insights. "
            "Focus on revenue growth, customer retention, and operational efficiency. "
            "Keep each point under 25 words. Reply with ONLY bullets, no intro."
        )
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile" if os.getenv("GROQ_API_KEY") else "local-model",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Analyze this hardware/e-commerce data:\n{context}"}
            ],
            temperature=0.3
        )

        raw_text = response.choices[0].message.content.strip()
        bullets = [b.strip().lstrip("-").lstrip("*").strip() for b in raw_text.split("\n") if b.strip()][:3]

        # 4. Persistence
        for i, text_content in enumerate(bullets, start=1):
            db.execute(text("""
                INSERT INTO insights (id, job_id, source_type, bullet_index, bullet_text, created_at)
                VALUES (gen_random_uuid(), :jid, 'ai_summary', :idx, :txt, NOW())
            """), {"jid": job_id, "idx": i, "txt": text_content})
        
        db.commit()
        logger.info(f"Saved {len(bullets)} AI insights for job {job_id}.")
        return {"status": "success", "count": len(bullets)}

    except Exception as e:
        db.rollback()
        logger.error(f"Insight generation failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()