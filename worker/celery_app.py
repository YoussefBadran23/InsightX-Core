"""
Celery Application Configuration for InsightX Worker.
Defines queues, routing, and Redis connection settings.
"""

import os
import sys
from celery import Celery

# Ensure the worker's own directory is on sys.path so the `tasks` package can be
# resolved even after Celery's `import_from_cwd` context has unwound. Without
# this, `autodiscover_tasks` and any later imports of `tasks.*` raise
# ModuleNotFoundError when invoked via the `celery` console script.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Explicit `include` resolves the task modules at app construction time,
# while celery_app.py is being imported by `celery -A celery_app`. That's
# more reliable than `autodiscover_tasks`, which defers resolution until
# after the cwd-on-path side-effect has gone.
celery_app = Celery(
    "insightx_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "tasks.stage3_preprocess",
        "tasks.stage4_upsert",
        "tasks.stage5_run_module",   # Single dynamic task that runs any registered module
        "tasks.stage6_finalize",
        # Importing tasks.analytics fires all 18 @register decorators at worker
        # startup, populating schema.MODULES[key].fn for the pipeline lookup.
        "tasks.analytics",
    ],
)

# ── Optimized Configuration ──
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Reliability settings
    broker_connection_retry_on_startup=True,
    task_acks_late=True,               # Don't ack until task succeeds
    worker_prefetch_multiplier=1,      # Fair distribution of heavy tasks
    
    # Redis memory hygiene
    result_expires=3600,               # Clear results after 1 hour
    
    # Task routing (Queue definition)
    task_routes={
        # Machine Learning tasks go to 'ml' queue
        "tasks.analytics.a15_*": {"queue": "ml"},
        "tasks.analytics.a16_*": {"queue": "ml"},
        "tasks.analytics.a17_*": {"queue": "ml"},
        "tasks.analytics.a18_*": {"queue": "ml"},
        "tasks.analytics.a19_*": {"queue": "ml"},
        "tasks.analytics.a20_*": {"queue": "ml"},
        "tasks.analytics.a23_*": {"queue": "ml"},
        "tasks.analytics.a24_*": {"queue": "ml"},
        "tasks.analytics.a26_*": {"queue": "ml"},
        
        # Standard analytics go to 'analytics' queue
        "tasks.analytics.*": {"queue": "analytics"},
        
        # Pipeline stages go to the default 'celery' queue
        "tasks.pipeline.*": {"queue": "celery"},
    }
)
