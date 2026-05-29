"""Lightweight Celery client used by the backend to dispatch tasks.

The backend never imports the full worker; it only needs to send task
messages to the broker. This singleton is reused across all requests.
"""

from celery import Celery
from app.core.config import settings

celery_client = Celery(
    "insightx_backend_client",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_client.conf.update(
    task_serializer="json",
    accept_content=["json"],
)
