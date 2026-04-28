"""Analytics Module Registry — Fully Mapped for Dynamic Execution."""
from dataclasses import dataclass, field

@dataclass(frozen=True)
class AnalyticsModule:
    key: str
    name: str
    name_ar: str
    description: str
    required_cols: frozenset[str]
    task_path: str
    optional_cols: frozenset[str] = field(default_factory=frozenset)
    queue: str = "analytics"

MODULES: dict[str, AnalyticsModule] = {}

def _register(m: AnalyticsModule) -> None:
    MODULES[m.key] = m

# ── Analytics Queue (A01 - A14) ───────────────────────────────────────────────

_register(AnalyticsModule(
    key="A01_revenue_summary",
    name="Revenue Summary",
    name_ar="ملخص الإيرادات",
    description="Total revenue breakdown by region, period, and category",
    required_cols=frozenset({"total_amount", "created_at"}),
    task_path="tasks.analytics.a01_revenue_summary.run_revenue_summary",
    optional_cols=frozenset({"region", "net_amount", "discount_amount", "category"}),
))

_register(AnalyticsModule(
    key="A02_rfm_scoring",
    name="RFM Scoring",
    name_ar="تحليل RFM",
    description="Recency, Frequency, Monetary scoring per customer",
    required_cols=frozenset({"customer_id", "total_amount", "created_at"}),
    task_path="tasks.analytics.a02_rfm_scoring.run_rfm_scoring",
))

_register(AnalyticsModule(
    key="A03_market_basket",
    name="Market Basket Analysis",
    name_ar="تحليل سلة المشتريات",
    description="Association rules — products bought together",
    required_cols=frozenset({"id", "product_id"}),
    task_path="tasks.analytics.a03_market_basket.run_market_basket",
    optional_cols=frozenset({"quantity"}),
))

_register(AnalyticsModule(
    key="A04_gross_margin",
    name="Gross Margin Analysis",
    name_ar="تحليل هامش الربح",
    description="Profit margin per product and category",
    required_cols=frozenset({"total_amount", "cost_amount"}),
    task_path="tasks.analytics.a04_gross_margin.run_gross_margin",
    optional_cols=frozenset({"product_id", "category"}),
))

_register(AnalyticsModule(
    key="A05_cohort_retention",
    name="Cohort Retention",
    name_ar="تحليل الاحتفاظ بالعملاء",
    description="Monthly cohort retention heatmap",
    required_cols=frozenset({"customer_id", "created_at"}),
    task_path="tasks.analytics.a05_cohort_retention.run_cohort_retention",
))

_register(AnalyticsModule(
    key="A06_geographic_revenue",
    name="Geographic Revenue",
    name_ar="الإيرادات الجغرافية",
    description="Revenue aggregated by region and country",
    required_cols=frozenset({"total_amount", "region"}),
    task_path="tasks.analytics.a06_geographic_revenue.run_geographic_revenue",
    optional_cols=frozenset({"country", "country_code"}),
))

_register(AnalyticsModule(
    key="A07_abc_classification",
    name="ABC Tier Classification",
    name_ar="تصنيف ABC",
    description="Pareto product revenue classification",
    required_cols=frozenset({"product_id", "total_amount"}),
    task_path="tasks.analytics.a07_abc_classification.run_abc_classification",
))

_register(AnalyticsModule(
    key="A08_aov_trends",
    name="Average Order Value Trends",
    name_ar="اتجاهات متوسط قيمة الطلب",
    description="AOV over time — daily, weekly, monthly",
    required_cols=frozenset({"total_amount", "created_at"}),
    task_path="tasks.analytics.a08_aov_trends.run_aov_trends",
))

_register(AnalyticsModule(
    key="A09_top_n_products",
    name="Top N Products",
    name_ar="أفضل المنتجات والفئات",
    description="Ranked products and categories by revenue",
    required_cols=frozenset({"product_id", "total_amount"}),
    task_path="tasks.analytics.a09_top_n_products.run_top_n_products",
))

_register(AnalyticsModule(
    key="A10_customer_lifetime",
    name="Customer Lifetime Stats",
    name_ar="إحصائيات عمر العميل",
    description="CLV distribution and average lifetime value",
    required_cols=frozenset({"customer_id", "total_amount"}),
    task_path="tasks.analytics.a10_customer_lifetime.run_customer_lifetime",
))

_register(AnalyticsModule(
    key="A11_order_status",
    name="Order Status Distribution",
    name_ar="توزيع حالة الطلبات",
    description="Breakdown of orders by status",
    required_cols=frozenset({"status"}),
    task_path="tasks.analytics.a11_order_status.run_order_status",
))

_register(AnalyticsModule(
    key="A12_discount_impact",
    name="Discount Impact Analysis",
    name_ar="تحليل تأثير الخصومات",
    description="How discounts affect revenue and volume",
    required_cols=frozenset({"total_amount", "discount_amount"}),
    task_path="tasks.analytics.a12_discount_impact.run_discount_impact",
))

_register(AnalyticsModule(
    key="A13_growth_rates",
    name="Period Growth",
    name_ar="معدلات النمو",
    description="MoM, QoQ, YoY revenue growth rates",
    required_cols=frozenset({"total_amount", "created_at"}),
    task_path="tasks.analytics.a13_growth_rates.run_growth_rates",
))

_register(AnalyticsModule(
    key="A14_acquisition_channel",
    name="Acquisition by Channel",
    name_ar="اكتساب العملاء حسب القناة",
    description="Revenue and customer count by source",
    required_cols=frozenset({"acquisition_channel", "customer_id"}),
    task_path="tasks.analytics.a14_acquisition_channel.run_acquisition_channel",
))

# ── ML Queue (A15 - A20) ──────────────────────────────────────────────────────

_register(AnalyticsModule(
    key="A15_prophet_forecast",
    name="Revenue Forecasting",
    name_ar="التنبؤ بالإيرادات",
    description="30/60/90-day revenue forecast",
    required_cols=frozenset({"total_amount", "created_at"}),
    task_path="tasks.analytics.a15_prophet_forecast.run_prophet_forecast",
    queue="ml",
))

_register(AnalyticsModule(
    key="A16_anomaly_detection",
    name="Anomaly Detection",
    name_ar="كشف الشذوذ",
    description="Detect outlier orders using Isolation Forest",
    required_cols=frozenset({"total_amount", "created_at"}),
    task_path="tasks.analytics.a16_anomaly_detection.run_anomaly_detection",
    queue="ml",
))

_register(AnalyticsModule(
    key="A17_clv_prediction",
    name="CLV Prediction",
    name_ar="توقع قيمة العميل",
    description="BG/NBD CLV prediction",
    required_cols=frozenset({"customer_id", "total_amount", "created_at"}),
    task_path="tasks.analytics.a17_clv_prediction.run_clv_prediction",
    queue="ml",
))

_register(AnalyticsModule(
    key="A18_sentiment_analysis",
    name="Sentiment Analysis",
    name_ar="تحليل المشاعر",
    description="Comment sentiment classification",
    required_cols=frozenset({"comment_text"}),
    task_path="tasks.analytics.a18_sentiment_analysis.run_sentiment_analysis",
    queue="ml",
))

_register(AnalyticsModule(
    key="A19_customer_segmentation",
    name="Customer Segmentation",
    name_ar="تقسيم العملاء",
    description="K-Means clustering on RFM features",
    required_cols=frozenset({"customer_id", "total_amount", "created_at"}),
    task_path="tasks.analytics.a19_customer_segmentation.run_customer_segmentation",
    queue="ml",
))

_register(AnalyticsModule(
    key="A20_churn_prediction",
    name="Churn Risk Prediction",
    name_ar="توقع مخاطر فقدان العملاء",
    description="Logistic regression churn scoring",
    required_cols=frozenset({"customer_id", "total_amount", "created_at"}),
    task_path="tasks.analytics.a20_churn_prediction.run_churn_prediction",
    queue="ml",
))

# ── Post-Chord (A21 - A22) ────────────────────────────────────────────────────

_register(AnalyticsModule(
    key="A21_return_rate",
    name="Return Rate Analysis",
    name_ar="تحليل معدل الإرجاع",
    description="Return rates per product and category",
    required_cols=frozenset({"return_flag", "product_id"}),
    task_path="tasks.analytics.a21_return_rate.run_return_rate",
))

_register(AnalyticsModule(
    key="A22_fulfillment_sla",
    name="Fulfillment SLA Analysis",
    name_ar="تحليل مستوى خدمة التوصيل",
    description="Delivery time distribution and compliance",
    required_cols=frozenset({"delivery_days"}),
    task_path="tasks.analytics.a22_fulfillment_sla.run_fulfillment_sla",
))

def check_eligibility(available_columns: set[str]) -> dict:
    """Check which modules can run based on provided column set."""
    results = {}
    for key, mod in MODULES.items():
        missing_req = mod.required_cols - available_columns
        results[key] = {
            "can_run": len(missing_req) == 0,
            "module": mod,
            "missing_required": list(missing_req),
        }
    return results