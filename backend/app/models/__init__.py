"""
InsightX ORM models package.
Import all models here so Alembic autogenerate picks them up via Base.metadata.
"""

from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.customer import Customer  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.upload_job import UploadJob  # noqa: F401
from app.models.csv_column_mapping import CsvColumnMapping  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.order_item import OrderItem  # noqa: F401
from app.models.forecast_result import ForecastResult  # noqa: F401
from app.models.daily_kpi_snapshot import DailyKpiSnapshot  # noqa: F401
from app.models.analysis_results_cache import AnalysisResultsCache  # noqa: F401
from app.models.insight import Insight  # noqa: F401

__all__ = [
    "User",
    "Customer",
    "Product",
    "UploadJob",
    "CsvColumnMapping",
    "Order",
    "OrderItem",
    "ForecastResult",
    "DailyKpiSnapshot",
    "AnalysisResultsCache",
    "Insight",
]
