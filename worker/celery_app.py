"""Celery application configuration with Task Routing and Reliability."""
import os
from celery import Celery
from dotenv import load_dotenv
import sentry_sdk
from ddtrace import patch_all, tracer

load_dotenv()

# Initialize Sentry for error tracking
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=os.getenv("APP_ENV", "development"),
        traces_sample_rate=1.0,
    )

# Initialize Datadog for monitoring
dd_api_key = os.getenv("DD_API_KEY")
if dd_api_key:
    patch_all()
    tracer.configure(
        hostname="datadog-agent",
        port=8126,
        service="insightx-worker",
        env=os.getenv("DD_ENV", "development"),
    )

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
    
    # RELIABILITY
    task_acks_late=True,             # Task stays in Redis until finished
    worker_prefetch_multiplier=1,    # One task per worker process at a time (saves RAM)
    task_reject_on_worker_lost=True, # Re-queue if the container crashes
    
    # TIME LIMITS
    task_soft_time_limit=300,        # 5 mins
    task_time_limit=360,             # 6 mins

    # TASK ROUTING
    task_routes={
        "tasks.analytics.*": {"queue": "analytics"},
        "tasks.forecast.*": {"queue": "ml"},
        "tasks.sentiment.*": {"queue": "ml"},
        "tasks.preprocess.*": {"queue": "analytics"},
        "tasks.csv.*": {"queue": "analytics"},
    },
)