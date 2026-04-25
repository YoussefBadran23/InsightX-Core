"""Celery application configuration."""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "insightx_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=[
        "tasks.csv",
        "tasks.preprocess",
        "tasks.upsert",
        "tasks.forecast",
        "tasks.sentiment",
        "tasks.insights",
        "tasks.finalize",
        "tasks.analytics",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Reliability: re-queue task if worker crashes mid-execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Time limits: soft warns at 4 min, hard kills at 5 min
    task_soft_time_limit=240,
    task_time_limit=300,
    # Dead-letter queue: failed tasks land in insightx.dlq on the broker
    task_queues={
        "celery": {
            "exchange": "celery",
            "routing_key": "celery",
            "queue_arguments": {
                "x-dead-letter-exchange": "insightx.dlq",
            },
        }
    },
)
