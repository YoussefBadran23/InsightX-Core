"""Analytics modules package.

Each module exposes a pure function `run(df) -> dict` decorated with
`@register(...)` from `_base`. The standalone runner (`worker/run_analytics.py`)
imports this package and iterates the registry. The Celery integration in
`stage4_upsert.py` will be wired up later, after we've validated each module
end-to-end on real seed data.
"""

# Importing each module file populates the ANALYTICS_REGISTRY. New modules
# are added below as they're implemented.
from . import a01_revenue_summary  # noqa: F401
from . import a02_rfm_scoring  # noqa: F401
from . import a03_market_basket  # noqa: F401
from . import a04_gross_margin  # noqa: F401
from . import a05_cohort_retention  # noqa: F401
from . import a06_geographic_revenue  # noqa: F401
from . import a07_abc_classification  # noqa: F401
from . import a08_aov_trends  # noqa: F401
from . import a09_top_n_products  # noqa: F401
from . import a10_customer_lifetime  # noqa: F401
from . import a11_order_status  # noqa: F401
from . import a12_discount_impact  # noqa: F401
from . import a13_growth_rates  # noqa: F401
from . import a14_acquisition_channel  # noqa: F401
from . import a15_prophet_forecast  # noqa: F401
from . import a16_anomaly_detection  # noqa: F401
from . import a17_clv_prediction  # noqa: F401
from . import a18_sentiment_analysis  # noqa: F401
from . import a19_customer_segmentation  # noqa: F401
from . import a20_churn_prediction  # noqa: F401
from . import a21_return_rate  # noqa: F401
from . import a22_fulfillment_sla  # noqa: F401
from . import a23_product_lifecycle  # noqa: F401
from . import a24_basket_recommendations  # noqa: F401
from . import a25_stockout_risk  # noqa: F401
from . import a26_sentiment_ltv  # noqa: F401
from . import c01_demographics  # noqa: F401
from . import c02_top_customers  # noqa: F401
from . import c03_geo_distribution  # noqa: F401
from . import c04_new_vs_returning  # noqa: F401
from . import c05_segment_breakdown  # noqa: F401
from . import c06_activity_timeline  # noqa: F401
from . import p01_product_ranking  # noqa: F401
from . import p02_category_performance  # noqa: F401
from . import p03_brand_performance  # noqa: F401
from . import p04_product_sales_trend  # noqa: F401
from . import p05_stock_health  # noqa: F401
from . import p06_return_heatmap  # noqa: F401
from . import p07_price_volume  # noqa: F401
