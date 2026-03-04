"""Placeholder — Step 10 (Phase 3): Data preprocessing from S3 CSVs."""

from celery_app import celery_app


@celery_app.task(bind=True, name="tasks.preprocess.run_preprocessing")
def run_preprocessing(self, job_id: str, s3_key: str):
    """Pull CSV from S3, clean NaNs, standardise dates, drop duplicates."""
    # TODO: Implement in Phase 3 (Step 10)
    raise NotImplementedError("Preprocessing task not yet implemented.")
