"""Celery application configuration."""

from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "insightx_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=[
        "tasks.preprocess",
        "tasks.forecast",
        "tasks.sentiment",
        "tasks.insights",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
