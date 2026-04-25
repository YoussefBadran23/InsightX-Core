"""Analytics module tasks (A01-A22).

Importing this package registers all 22 Celery tasks via the @analytics_task decorator.
"""

from .a01_revenue_summary import run_revenue_summary
from .a02_rfm_scoring import run_rfm_scoring
from .a03_market_basket import run_market_basket
from .a04_gross_margin import run_gross_margin
from .a05_cohort_retention import run_cohort_retention
from .a06_geographic_revenue import run_geographic_revenue
from .a07_abc_classification import run_abc_classification
from .a08_aov_trends import run_aov_trends
from .a09_top_n_products import run_top_n_products
from .a10_customer_lifetime import run_customer_lifetime
from .a11_order_status import run_order_status
from .a12_discount_impact import run_discount_impact
from .a13_growth_rates import run_growth_rates
from .a14_acquisition_channel import run_acquisition_channel
from .a15_prophet_forecast import run_prophet_forecast
from .a16_anomaly_detection import run_anomaly_detection
from .a17_clv_prediction import run_clv_prediction
from .a18_sentiment_analysis import run_sentiment_analysis
from .a19_customer_segmentation import run_customer_segmentation
from .a20_churn_prediction import run_churn_prediction
from .a21_return_rate import run_return_rate
from .a22_fulfillment_sla import run_fulfillment_sla

__all__ = [
    "run_revenue_summary",
    "run_rfm_scoring",
    "run_market_basket",
    "run_gross_margin",
    "run_cohort_retention",
    "run_geographic_revenue",
    "run_abc_classification",
    "run_aov_trends",
    "run_top_n_products",
    "run_customer_lifetime",
    "run_order_status",
    "run_discount_impact",
    "run_growth_rates",
    "run_acquisition_channel",
    "run_prophet_forecast",
    "run_anomaly_detection",
    "run_clv_prediction",
    "run_sentiment_analysis",
    "run_customer_segmentation",
    "run_churn_prediction",
    "run_return_rate",
    "run_fulfillment_sla",
]
