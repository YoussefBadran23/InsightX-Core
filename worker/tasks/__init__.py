"""
InsightX Core Tasks Package.

Exposes the primary entry points for the multi-stage ingestion and 
analytical pipeline, facilitating clean imports in the Celery app.
"""

from .csv import process_csv
from .preprocess import run_preprocessing
from .upsert import run_upserts
from .insights import run_insights
from .finalize import run_finalize

# Note: forecast and sentiment are currently exposed via the analytics package 
# and specific sub-modules A15 and A18.

__all__ = [
    "process_csv",
    "run_preprocessing",
    "run_upserts",
    "run_insights",
    "run_finalize",
]