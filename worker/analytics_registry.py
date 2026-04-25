"""Analytics Module Registry — declares required & optional columns for each of the 22 modules.

After CSV validation (Stage 3), the preprocess task checks which DB columns
are available and computes which modules CAN run vs which are blocked.

Each module entry contains:
  - name:          Human-readable display name
  - description:   One-line description of what it does
  - required_cols: Set of DB column names that MUST exist for this module to run
  - optional_cols: Set of DB column names that enhance output but aren't mandatory
  - queue:         Which Celery queue this runs on (analytics | ml)
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalyticsModule:
    key: str
    name: str
    name_ar: str
    description: str
    required_cols: frozenset[str]
    optional_cols: frozenset[str] = field(default_factory=frozenset)
    queue: str = "analytics"


# ── The 22 Analytics Modules ─────────────────────────────────────────────────

MODULES: dict[str, AnalyticsModule] = {}

def _register(m: AnalyticsModule) -> None:
    MODULES[m.key] = m


# ── Analytics Queue (14 tasks) ───────────────────────────────────────────────

_register(AnalyticsModule(
    key="A01_revenue_summary",
    name="Revenue Summary",
    name_ar="ملخص الإيرادات",
    description="Total revenue breakdown by region, period, and category",
    required_cols=frozenset({"total_amount", "created_at"}),
    optional_cols=frozenset({"region", "net_amount", "discount_amount", "currency"}),
))

_register(AnalyticsModule(
    key="A02_rfm_scoring",
    name="RFM Scoring",
    name_ar="تحليل RFM",
    description="Recency, Frequency, Monetary scoring per customer → segment labels",
    required_cols=frozenset({"customer_id", "total_amount", "created_at"}),
    optional_cols=frozenset({"net_amount"}),
))

_register(AnalyticsModule(
    key="A03_market_basket",
    name="Market Basket Analysis",
    name_ar="تحليل سلة المشتريات",
    description="Association rules — which products are frequently bought together",
    required_cols=frozenset({"id", "product_id"}),
    optional_cols=frozenset({"quantity"}),
))

_register(AnalyticsModule(
    key="A04_gross_margin",
    name="Gross Margin Analysis",
    name_ar="تحليل هامش الربح",
    description="Profit margin per product and category",
    required_cols=frozenset({"total_amount", "cost_amount"}),
    optional_cols=frozenset({"product_id", "category", "net_amount"}),
))

_register(AnalyticsModule(
    key="A05_cohort_retention",
    name="Cohort Retention",
    name_ar="تحليل الاحتفاظ بالعملاء",
    description="Monthly cohort retention heatmap",
    required_cols=frozenset({"customer_id", "created_at"}),
    optional_cols=frozenset({"total_amount"}),
))

_register(AnalyticsModule(
    key="A06_geographic_revenue",
    name="Geographic Revenue",
    name_ar="الإيرادات الجغرافية",
    description="Revenue aggregated by region and country",
    required_cols=frozenset({"total_amount", "region"}),
    optional_cols=frozenset({"country", "country_code", "created_at"}),
))

_register(AnalyticsModule(
    key="A07_abc_classification",
    name="ABC Tier Classification",
    name_ar="تصنيف ABC",
    description="Pareto 80/20 product revenue classification (A/B/C tiers)",
    required_cols=frozenset({"product_id", "total_amount"}),
    optional_cols=frozenset({"quantity", "unit_price"}),
))

_register(AnalyticsModule(
    key="A08_aov_trends",
    name="Average Order Value Trends",
    name_ar="اتجاهات متوسط قيمة الطلب",
    description="AOV over time — daily, weekly, monthly trends",
    required_cols=frozenset({"total_amount", "created_at"}),
    optional_cols=frozenset({"net_amount", "region"}),
))

_register(AnalyticsModule(
    key="A09_top_n_products",
    name="Top N Products / Categories",
    name_ar="أفضل المنتجات والفئات",
    description="Ranked products and categories by revenue and units sold",
    required_cols=frozenset({"product_id", "total_amount"}),
    optional_cols=frozenset({"quantity", "category", "unit_price"}),
))

_register(AnalyticsModule(
    key="A10_customer_lifetime",
    name="Customer Lifetime Stats",
    name_ar="إحصائيات عمر العميل",
    description="CLV distribution, average lifetime value, percentiles",
    required_cols=frozenset({"customer_id", "total_amount"}),
    optional_cols=frozenset({"created_at", "net_amount"}),
))

_register(AnalyticsModule(
    key="A11_order_status",
    name="Order Status Distribution",
    name_ar="توزيع حالة الطلبات",
    description="Breakdown of orders by status (completed, refunded, cancelled, pending)",
    required_cols=frozenset({"status"}),
    optional_cols=frozenset({"total_amount", "created_at", "region"}),
))

_register(AnalyticsModule(
    key="A12_discount_impact",
    name="Discount Impact Analysis",
    name_ar="تحليل تأثير الخصومات",
    description="How discounts affect revenue, AOV, and order volume",
    required_cols=frozenset({"total_amount", "discount_amount"}),
    optional_cols=frozenset({"created_at", "net_amount", "region"}),
))

_register(AnalyticsModule(
    key="A13_growth_rates",
    name="Period-over-Period Growth",
    name_ar="معدلات النمو",
    description="MoM, QoQ, YoY revenue and order growth rates",
    required_cols=frozenset({"total_amount", "created_at"}),
    optional_cols=frozenset({"net_amount", "region"}),
))

_register(AnalyticsModule(
    key="A14_acquisition_channel",
    name="Customer Acquisition by Channel",
    name_ar="اكتساب العملاء حسب القناة",
    description="Revenue and customer count split by acquisition channel",
    required_cols=frozenset({"acquisition_channel", "customer_id"}),
    optional_cols=frozenset({"total_amount", "created_at"}),
))

# ── ML Queue (6 tasks) ──────────────────────────────────────────────────────

_register(AnalyticsModule(
    key="A15_prophet_forecast",
    name="Revenue Forecasting (Prophet)",
    name_ar="التنبؤ بالإيرادات",
    description="30/60/90-day revenue forecast with confidence intervals",
    required_cols=frozenset({"total_amount", "created_at"}),
    optional_cols=frozenset({"net_amount", "region"}),
    queue="ml",
))

_register(AnalyticsModule(
    key="A16_anomaly_detection",
    name="Anomaly Detection",
    name_ar="كشف الشذوذ",
    description="Isolation Forest to detect outlier orders",
    required_cols=frozenset({"total_amount", "created_at"}),
    optional_cols=frozenset({"quantity", "customer_id", "region"}),
    queue="ml",
))

_register(AnalyticsModule(
    key="A17_clv_prediction",
    name="CLV Prediction (BG/NBD)",
    name_ar="توقع قيمة العميل",
    description="Customer lifetime value prediction using BG/NBD + Gamma-Gamma",
    required_cols=frozenset({"customer_id", "total_amount", "created_at"}),
    optional_cols=frozenset({"net_amount"}),
    queue="ml",
))

_register(AnalyticsModule(
    key="A18_sentiment_analysis",
    name="Sentiment Analysis (LLM)",
    name_ar="تحليل المشاعر",
    description="Order comment sentiment classification via Local LLM",
    required_cols=frozenset({"comment_text"}),
    optional_cols=frozenset({"customer_id", "product_id", "created_at"}),
    queue="ml",
))

_register(AnalyticsModule(
    key="A19_customer_segmentation",
    name="Customer Segmentation (K-Means)",
    name_ar="تقسيم العملاء",
    description="K-Means clustering on RFM features → AI segment labels",
    required_cols=frozenset({"customer_id", "total_amount", "created_at"}),
    optional_cols=frozenset({"net_amount", "region"}),
    queue="ml",
))

_register(AnalyticsModule(
    key="A20_churn_prediction",
    name="Churn Risk Prediction",
    name_ar="توقع مخاطر فقدان العملاء",
    description="Logistic regression churn risk scoring per customer",
    required_cols=frozenset({"customer_id", "total_amount", "created_at"}),
    optional_cols=frozenset({"net_amount", "region", "status"}),
    queue="ml",
))

# ── Post-Chord (2 tasks) ────────────────────────────────────────────────────

_register(AnalyticsModule(
    key="A21_return_rate",
    name="Return Rate Analysis",
    name_ar="تحليل معدل الإرجاع",
    description="Return rates per product and category",
    required_cols=frozenset({"return_flag", "product_id"}),
    optional_cols=frozenset({"total_amount", "category", "quantity"}),
))

_register(AnalyticsModule(
    key="A22_fulfillment_sla",
    name="Fulfillment SLA Analysis",
    name_ar="تحليل مستوى خدمة التوصيل",
    description="Delivery time distribution and SLA compliance",
    required_cols=frozenset({"delivery_days"}),
    optional_cols=frozenset({"region", "created_at", "product_id", "status"}),
))


# ── Eligibility checker ─────────────────────────────────────────────────────

def check_eligibility(available_columns: set[str]) -> dict[str, dict]:
    """
    Given the set of DB column names present after validation,
    return a dict of module_key → eligibility info.

    Each entry:
      {
        "can_run": True/False,
        "module": AnalyticsModule,
        "missing_required": set of missing required cols,
        "missing_optional": set of missing optional cols,
        "available_required": set of present required cols,
      }
    """
    results = {}
    for key, mod in MODULES.items():
        missing_req = mod.required_cols - available_columns
        missing_opt = mod.optional_cols - available_columns
        results[key] = {
            "can_run": len(missing_req) == 0,
            "module": mod,
            "missing_required": missing_req,
            "missing_optional": missing_opt,
            "available_required": mod.required_cols & available_columns,
        }
    return results
