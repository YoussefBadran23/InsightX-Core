"""
InsightX Gold Standard Schema and Analytics Module Registry.
Single source of truth for the backend sniff endpoint, worker pipeline, and frontend.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, FrozenSet

# ── 1. SCHEMA DEFINITIONS ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ColumnDefinition:
    internal_column: str
    display_name: str
    group: str
    aliases: List[str]

COLUMNS: List[ColumnDefinition] = [
    # ── Transaction Core (16) ──
    # Each column carries English + Arabic aliases so dirty_ar_02_messy_headers
    # (all-Arabic header names) maps cleanly. New aliases can be added without
    # touching anywhere else — the upload sniff endpoint and run_matrix.py both
    # read from this list.
    ColumnDefinition("order_id", "Order ID", "transaction", [
        "invoice", "transaction_id", "order_number", "receipt_id",
        "رقم الطلب", "رقم_الطلب", "معرف الطلب", "رقم الفاتورة",
    ]),
    ColumnDefinition("order_date", "Order Date", "transaction", [
        "date", "purchase_date", "timestamp", "created_at", "sale_date",
        "تاريخ الطلب", "تاريخ_الطلب", "تاريخ الشراء", "التاريخ",
    ]),
    ColumnDefinition("customer_id", "Customer ID", "transaction", [
        "client_id", "user_id", "buyer_id", "account_id",
        "معرف الزبون", "معرف_الزبون", "رقم العميل", "رقم الزبون", "معرف العميل",
    ]),
    ColumnDefinition("total_amount", "Total Amount", "transaction", [
        "revenue", "price", "sale_amount", "gross_amount", "total",
        "amount", "amount_spent", "amount_spent_usd", "total_spent", "total_price",
        "المبلغ الإجمالي", "المبلغ_الاجمالي", "الإجمالي", "إجمالي المبلغ", "السعر الإجمالي",
    ]),
    ColumnDefinition("net_amount", "Net Amount", "transaction", [
        "net_revenue", "net_sales", "revenue_after_discount",
        "صافي المبيعات", "صافي_المبيعات", "صافي المبلغ", "صافي الإيرادات",
    ]),
    ColumnDefinition("cost_amount", "Cost / COGS", "transaction", [
        "cogs", "cost_price", "unit_cost", "cost_of_goods",
        "تكلفة البضاعة", "تكلفة_البضاعة", "التكلفة", "تكلفة المنتج",
    ]),
    ColumnDefinition("discount_amount", "Discount Amount", "transaction", [
        "discount", "coupon_amount", "promo_amount",
        "قيمة الخصم", "قيمة_الخصم", "الخصم", "مبلغ الخصم",
    ]),
    ColumnDefinition("product_id", "Product ID", "transaction", [
        "sku", "item_id", "product_code", "product_ref",
        "رمز المنتج", "رمز_المنتج", "معرف المنتج", "رقم المنتج",
    ]),
    ColumnDefinition("quantity", "Quantity", "transaction", [
        "qty", "units", "items_sold", "count",
        "الكمية", "العدد", "كمية",
    ]),
    ColumnDefinition("unit_price", "Unit Price", "transaction", [
        "item_price", "price_per_unit", "selling_price",
        "سعر الوحدة", "سعر_الوحدة", "السعر",
    ]),
    ColumnDefinition("status", "Order Status", "transaction", [
        "order_status", "fulfillment_status", "state",
        "حالة الطلب", "حالة_الطلب", "الحالة",
    ]),
    ColumnDefinition("return_flag", "Return Flag", "transaction", [
        "is_returned", "returned", "refunded", "return_status",
        "هل تم الإرجاع", "هل_تم_الإرجاع", "تم الإرجاع", "مرتجع", "الإرجاع",
    ]),
    ColumnDefinition("delivery_days", "Delivery Days", "transaction", [
        "days_to_deliver", "fulfillment_days", "shipping_days",
        "أيام التوصيل", "ايام_التوصيل", "أيام_التوصيل", "مدة التوصيل",
    ]),
    ColumnDefinition("acquisition_channel", "Acquisition Channel", "transaction", [
        "source", "channel", "utm_source", "marketing_source",
        "قناة التسويق", "قناة_التسويق", "مصدر العميل", "قناة الاستحواذ",
    ]),
    ColumnDefinition("payment_method", "Payment Method", "transaction", [
        "payment_type", "pay_method",
        "طريقة الدفع", "طريقة_الدفع", "وسيلة الدفع",
    ]),
    ColumnDefinition("currency", "Currency", "transaction", [
        "currency_code", "fx",
        "العملة", "عملة",
    ]),

    # ── Customer Metadata (14) ──
    ColumnDefinition("customer_name", "Customer Name", "customer_meta", [
        "name", "full_name", "client_name", "buyer_name",
        "اسم الزبون", "اسم_الزبون", "اسم العميل", "اسم_العميل", "الاسم",
    ]),
    ColumnDefinition("customer_email", "Customer Email", "customer_meta", [
        "email", "email_address", "contact_email",
        "البريد الإلكتروني", "البريد_الالكتروني", "البريد الالكتروني", "الإيميل", "ايميل",
    ]),
    ColumnDefinition("customer_phone", "Customer Phone", "customer_meta", [
        "phone", "mobile", "telephone", "contact_number",
        "رقم الجوال", "رقم_الجوال", "الجوال", "الهاتف", "رقم الهاتف",
    ]),
    ColumnDefinition("customer_city", "City", "customer_meta", [
        "city", "town", "customer_city",
        "المدينة", "مدينة الزبون",
    ]),
    ColumnDefinition("region", "Region", "customer_meta", [
        "area", "territory", "zone", "sales_region",
        "المنطقة", "المنطقه", "المنطقة الجغرافية",
    ]),
    ColumnDefinition("country", "Country", "customer_meta", [
        "country_name", "nation", "customer_country", "buyer_country", "shipping_country",
        "الدولة", "البلد", "اسم الدولة",
    ]),
    ColumnDefinition("country_code", "Country Code", "customer_meta", [
        "iso_code", "cc",
        "رمز الدولة", "رمز_الدولة", "كود الدولة",
    ]),
    ColumnDefinition("gender", "Gender", "customer_meta", [
        "sex", "customer_gender",
        "الجنس",
    ]),
    ColumnDefinition("age", "Age", "customer_meta", [
        "customer_age", "age_years",
        "العمر", "السن",
    ]),
    ColumnDefinition("birth_date", "Birth Date", "customer_meta", [
        "dob", "date_of_birth", "birthday",
        "تاريخ الميلاد", "تاريخ_الميلاد", "الميلاد",
    ]),
    ColumnDefinition("customer_segment", "Customer Segment", "customer_meta", [
        "segment", "tier", "customer_tier", "vip_status",
        "تصنيف الزبون", "تصنيف_الزبون", "فئة العميل", "شريحة العميل",
    ]),
    ColumnDefinition("loyalty_points", "Loyalty Points", "customer_meta", [
        "points", "reward_points", "loyalty_score",
        "نقاط الولاء", "نقاط_الولاء", "النقاط",
    ]),
    ColumnDefinition("registration_date", "Registration Date", "customer_meta", [
        "signup_date", "join_date", "member_since",
        "تاريخ التسجيل", "تاريخ_التسجيل", "تاريخ الانضمام",
    ]),
    ColumnDefinition("comment_text", "Review / Comment", "customer_meta", [
        "review", "feedback", "comment", "notes", "customer_note",
        "ملاحظات الزبون", "ملاحظات_الزبون", "التعليق", "المراجعة", "تعليق",
    ]),

    # ── Product Metadata (9) ──
    ColumnDefinition("product_name", "Product Name", "product_meta", [
        "name", "item_name", "product_title", "product_label",
        "اسم المنتج", "اسم_المنتج", "اسم المنتجات",
    ]),
    ColumnDefinition("category", "Category", "product_meta", [
        "product_category", "cat", "product_type", "item_category",
        "الفئة", "التصنيف", "النوع",
    ]),
    ColumnDefinition("subcategory", "Subcategory", "product_meta", [
        "sub_category", "product_subcategory", "sub_cat",
        "الفئة الفرعية", "الفئة_الفرعية", "التصنيف الفرعي",
    ]),
    ColumnDefinition("brand", "Brand", "product_meta", [
        "brand_name", "manufacturer", "vendor_name",
        "العلامة التجارية", "العلامة_التجارية", "الماركة",
    ]),
    ColumnDefinition("product_description", "Description", "product_meta", [
        "description", "product_desc", "item_description",
        "وصف المنتج", "وصف_المنتج", "الوصف",
    ]),
    ColumnDefinition("product_status", "Product Status", "product_meta", [
        "item_status", "active", "is_active", "availability",
        "listing_status", "listing", "product_state",
        "حالة المنتج", "حالة_المنتج", "نشط",
    ]),
    ColumnDefinition("stock_qty", "Stock Quantity", "product_meta", [
        "inventory", "stock_level", "stock", "on_hand",
        "كمية المخزون", "كمية_المخزون", "المخزون", "الكمية المتوفرة",
    ]),
    ColumnDefinition("supplier", "Supplier", "product_meta", [
        "vendor", "supplier_name",
        "المورد", "المزود", "الموزع",
    ]),
    ColumnDefinition("reorder_level", "Reorder Level", "product_meta", [
        "min_stock", "reorder_point", "safety_stock",
        "حد إعادة الطلب", "حد_إعادة_الطلب", "حد الطلب", "نقطة إعادة الطلب",
    ]),
]

# Fast lookup dictionary
COLUMN_MAP: Dict[str, ColumnDefinition] = {col.internal_column: col for col in COLUMNS}

# ── 2. MODULE DEFINITIONS ───────────────────────────────────────────────────

@dataclass
class AnalyticsModule:
    key: str
    name: str
    name_ar: str
    description: str
    required_cols: FrozenSet[str]
    series: str
    optional_cols: FrozenSet[str] = field(default_factory=frozenset)
    queue: str = "analytics"
    # Populated at worker import time by the @register decorator in
    # tasks/analytics/_base.py. `fn` is the pure run(df) -> dict function;
    # `analysis_type` is the cache row's analysis_type column.
    fn: Optional[Callable[..., Dict[str, Any]]] = None
    analysis_type: str = ""

    def __hash__(self) -> int:
        # We need AnalyticsModule to be hashable for use as a dict value
        # in places that pickle it (Celery). Hash by key (always unique).
        return hash(self.key)

MODULES: Dict[str, AnalyticsModule] = {}

def _register(m: AnalyticsModule) -> None:
    MODULES[m.key] = m

# ── A-Series (Transaction) ──
_register(AnalyticsModule(
    key="A01_revenue_summary", name="Revenue Summary", name_ar="ملخص الإيرادات",
    description="Total revenue breakdown by region, period, and category",
    required_cols=frozenset({"total_amount", "order_date"}),
    optional_cols=frozenset({"net_amount", "region", "currency", "discount_amount"}),
    series="A"
))
_register(AnalyticsModule(
    key="A02_rfm_scoring", name="RFM Scoring", name_ar="تحليل RFM",
    description="Recency, Frequency, Monetary scoring per customer",
    required_cols=frozenset({"customer_id", "total_amount", "order_date"}),
    series="A"
))
_register(AnalyticsModule(
    key="A03_market_basket", name="Market Basket Analysis", name_ar="تحليل سلة المشتريات",
    description="Association rules — products bought together",
    required_cols=frozenset({"order_id", "product_id"}),
    optional_cols=frozenset({"quantity"}),
    series="A"
))
_register(AnalyticsModule(
    key="A04_gross_margin", name="Gross Margin Analysis", name_ar="تحليل هامش الربح",
    description="Profit margin per product and category",
    required_cols=frozenset({"total_amount", "cost_amount"}),
    optional_cols=frozenset({"product_id", "category"}),
    series="A"
))
_register(AnalyticsModule(
    key="A05_cohort_retention", name="Cohort Retention", name_ar="تحليل الاحتفاظ بالعملاء",
    description="Monthly cohort retention heatmap",
    required_cols=frozenset({"customer_id", "order_date"}),
    optional_cols=frozenset({"registration_date"}),
    series="A"
))
_register(AnalyticsModule(
    key="A06_geographic_revenue", name="Geographic Revenue", name_ar="الإيرادات الجغرافية",
    description="Revenue aggregated by region and country",
    required_cols=frozenset({"total_amount", "region"}),
    optional_cols=frozenset({"country", "country_code", "customer_city"}),
    series="A"
))
_register(AnalyticsModule(
    key="A07_abc_classification", name="ABC Tier Classification", name_ar="تصنيف ABC",
    description="Pareto product revenue classification",
    required_cols=frozenset({"product_id", "total_amount"}),
    optional_cols=frozenset({"category"}),
    series="A"
))
_register(AnalyticsModule(
    key="A08_aov_trends", name="Average Order Value Trends", name_ar="اتجاهات متوسط قيمة الطلب",
    description="AOV over time — daily, weekly, monthly",
    required_cols=frozenset({"total_amount", "order_date"}),
    series="A"
))
_register(AnalyticsModule(
    key="A09_top_n_products", name="Top N Products", name_ar="أفضل المنتجات",
    description="Ranked products and categories by revenue",
    required_cols=frozenset({"product_id", "total_amount"}),
    optional_cols=frozenset({"quantity", "category", "product_name"}),
    series="A"
))
_register(AnalyticsModule(
    key="A10_customer_lifetime", name="Customer Lifetime Stats", name_ar="إحصائيات عمر العميل",
    description="CLV distribution and average lifetime value",
    required_cols=frozenset({"customer_id", "total_amount"}),
    optional_cols=frozenset({"order_date"}),
    series="A"
))
_register(AnalyticsModule(
    key="A11_order_status", name="Order Status Distribution", name_ar="توزيع حالة الطلبات",
    description="Breakdown of orders by status",
    required_cols=frozenset({"status"}),
    series="A"
))
_register(AnalyticsModule(
    key="A12_discount_impact", name="Discount Impact Analysis", name_ar="تحليل تأثير الخصومات",
    description="How discounts affect revenue and volume",
    required_cols=frozenset({"total_amount", "discount_amount"}),
    optional_cols=frozenset({"net_amount"}),
    series="A"
))
_register(AnalyticsModule(
    key="A13_growth_rates", name="Period Growth Rates", name_ar="معدلات النمو",
    description="MoM, QoQ, YoY revenue growth rates",
    required_cols=frozenset({"total_amount", "order_date"}),
    optional_cols=frozenset({"net_amount"}),
    series="A"
))
_register(AnalyticsModule(
    key="A14_acquisition_channel", name="Acquisition by Channel", name_ar="اكتساب العملاء حسب القناة",
    description="Revenue and customer count by source",
    required_cols=frozenset({"acquisition_channel", "customer_id"}),
    optional_cols=frozenset({"total_amount"}),
    series="A"
))
_register(AnalyticsModule(
    key="A15_prophet_forecast", name="Revenue Forecasting (Prophet)", name_ar="التنبؤ بالإيرادات",
    description="30/60/90-day revenue forecast",
    required_cols=frozenset({"total_amount", "order_date"}),
    series="A", queue="ml"
))
_register(AnalyticsModule(
    key="A16_anomaly_detection", name="Anomaly Detection", name_ar="كشف الشذوذ",
    description="Detect outlier orders using Isolation Forest",
    required_cols=frozenset({"total_amount", "order_date"}),
    series="A", queue="ml"
))
_register(AnalyticsModule(
    key="A17_clv_prediction", name="CLV Prediction (BG/NBD)", name_ar="توقع قيمة العميل",
    description="BG/NBD CLV prediction",
    required_cols=frozenset({"customer_id", "total_amount", "order_date"}),
    series="A", queue="ml"
))
_register(AnalyticsModule(
    key="A18_sentiment_analysis", name="Sentiment Analysis (BERT)", name_ar="تحليل المشاعر",
    description="Comment sentiment classification",
    required_cols=frozenset({"comment_text"}),
    series="A", queue="ml"
))
_register(AnalyticsModule(
    key="A19_customer_segmentation", name="Customer Segmentation", name_ar="تقسيم العملاء",
    description="K-Means clustering on RFM features",
    required_cols=frozenset({"customer_id", "total_amount", "order_date"}),
    optional_cols=frozenset({"customer_segment"}),
    series="A", queue="ml"
))
_register(AnalyticsModule(
    key="A20_churn_prediction", name="Churn Risk Prediction", name_ar="توقع مخاطر فقدان العملاء",
    description="Logistic regression churn scoring",
    required_cols=frozenset({"customer_id", "total_amount", "order_date"}),
    series="A", queue="ml"
))
_register(AnalyticsModule(
    key="A21_return_rate", name="Return Rate Analysis", name_ar="تحليل معدل الإرجاع",
    description="Return rates per product and category",
    required_cols=frozenset({"return_flag", "product_id"}),
    optional_cols=frozenset({"total_amount"}),
    series="A"
))
_register(AnalyticsModule(
    key="A22_fulfillment_sla", name="Fulfillment SLA Analysis", name_ar="تحليل مستوى خدمة التوصيل",
    description="Delivery time distribution and compliance",
    required_cols=frozenset({"delivery_days"}),
    optional_cols=frozenset({"status"}),
    series="A"
))
_register(AnalyticsModule(
    key="A23_product_lifecycle", name="Product Life-Cycle Decay", name_ar="دورة حياة المنتج",
    description="Product sales velocity over time",
    required_cols=frozenset({"product_id", "total_amount", "order_date"}),
    optional_cols=frozenset({"quantity", "product_status"}),
    series="A", queue="ml"
))
_register(AnalyticsModule(
    key="A24_basket_recommendations", name="Market Basket Recommendations", name_ar="توصيات سلة المشتريات",
    description="Product recommendations based on co-occurrence",
    required_cols=frozenset({"order_id", "product_id", "quantity"}),
    optional_cols=frozenset({"product_name"}),
    series="A", queue="ml"
))
_register(AnalyticsModule(
    key="A25_stockout_risk", name="Stock-Out Risk", name_ar="مخاطر نفاد المخزون",
    description="Predicting when products will run out of stock",
    required_cols=frozenset({"product_id", "quantity", "stock_qty"}),
    optional_cols=frozenset({"order_date", "reorder_level"}),
    series="A"
))
_register(AnalyticsModule(
    key="A26_sentiment_ltv", name="Sentiment vs. LTV Correlation", name_ar="ارتباط المشاعر بقيمة العميل",
    description="How sentiment impacts long-term spend",
    required_cols=frozenset({"comment_text", "customer_id", "total_amount"}),
    optional_cols=frozenset({"order_date"}),
    series="A", queue="ml"
))

# ── C-Series (Customer) ──
_register(AnalyticsModule(
    key="C01_demographics", name="Customer Demographics", name_ar="التركيبة السكانية للعملاء",
    description="Age and gender distribution",
    # Required is dynamically OR'd between gender/age/birth_date, handled in eligibility
    required_cols=frozenset(), 
    optional_cols=frozenset({"gender", "age", "birth_date"}),
    series="C"
))
_register(AnalyticsModule(
    key="C02_top_customers", name="Top Customers by Revenue", name_ar="أفضل العملاء حسب الإيرادات",
    description="Ranked leaderboard card with spend",
    required_cols=frozenset({"customer_id", "total_amount"}),
    optional_cols=frozenset({"customer_name", "customer_email"}),
    series="C"
))
_register(AnalyticsModule(
    key="C03_geo_distribution", name="Customer Geographic Distribution", name_ar="التوزيع الجغرافي للعملاء",
    description="Map of where customers are located",
    required_cols=frozenset({"customer_id"}), # city OR region required, handled in eligibility
    optional_cols=frozenset({"customer_city", "region", "country"}),
    series="C"
))
_register(AnalyticsModule(
    key="C04_new_vs_returning", name="New vs Returning Customers", name_ar="العملاء الجدد مقابل العائدين",
    description="Trend line of new acquisitions",
    required_cols=frozenset({"customer_id", "order_date"}),
    optional_cols=frozenset({"registration_date"}),
    series="C"
))
_register(AnalyticsModule(
    key="C05_segment_breakdown", name="Customer Segment Breakdown", name_ar="تقسيم قطاعات العملاء",
    description="Pie chart of customer segments",
    required_cols=frozenset({"customer_id", "customer_segment"}),
    optional_cols=frozenset({"total_amount"}),
    series="C"
))
_register(AnalyticsModule(
    key="C06_activity_timeline", name="Customer Activity Timeline", name_ar="الجدول الزمني لنشاط العميل",
    description="Per-customer purchase history",
    required_cols=frozenset({"customer_id", "order_date", "total_amount"}),
    optional_cols=frozenset({"product_id", "status"}),
    series="C"
))

# ── P-Series (Product) ──
_register(AnalyticsModule(
    key="P01_product_ranking", name="Product Revenue Ranking", name_ar="تصنيف إيرادات المنتجات",
    description="Top/bottom performers table",
    required_cols=frozenset({"product_id", "total_amount"}),
    optional_cols=frozenset({"product_name", "category"}),
    series="P"
))
_register(AnalyticsModule(
    key="P02_category_performance", name="Category Performance", name_ar="أداء الفئة",
    description="Revenue by category over time",
    required_cols=frozenset({"category", "total_amount"}),
    optional_cols=frozenset({"order_date", "subcategory"}),
    series="P"
))
_register(AnalyticsModule(
    key="P03_brand_performance", name="Brand Performance", name_ar="أداء العلامة التجارية",
    description="Revenue by brand bar chart",
    required_cols=frozenset({"brand", "total_amount"}),
    optional_cols=frozenset({"product_id"}),
    series="P"
))
_register(AnalyticsModule(
    key="P04_product_sales_trend", name="Product Sales Trend", name_ar="اتجاه مبيعات المنتجات",
    description="Time-series line per product",
    required_cols=frozenset({"product_id", "total_amount", "order_date"}),
    optional_cols=frozenset({"product_name"}),
    series="P"
))
_register(AnalyticsModule(
    key="P05_stock_health", name="Stock Health Dashboard", name_ar="لوحة صحة المخزون",
    description="Traffic-light stock status",
    required_cols=frozenset({"product_id", "stock_qty"}),
    optional_cols=frozenset({"reorder_level", "product_name"}),
    series="P"
))
_register(AnalyticsModule(
    key="P06_return_heatmap", name="Product Return Heatmap", name_ar="خريطة حرارية لإرجاع المنتجات",
    description="Which products get returned most",
    required_cols=frozenset({"product_id", "return_flag"}),
    optional_cols=frozenset({"product_name", "category"}),
    series="P"
))
_register(AnalyticsModule(
    key="P07_price_volume", name="Price vs Volume Analysis", name_ar="تحليل السعر مقابل الحجم",
    description="Price sensitivity scatter plot",
    required_cols=frozenset({"product_id", "unit_price", "quantity"}),
    optional_cols=frozenset({"product_name", "category"}),
    series="P"
))

# ── 3. ELIGIBILITY LOGIC ────────────────────────────────────────────────────

def check_eligibility(available_columns: set[str]) -> dict:
    """
    Checks which modules can run based on the provided confirmed internal columns.
    Handles dynamic OR conditions for C01 and C03.
    """
    results = {}
    for key, mod in MODULES.items():
        missing_req = set(mod.required_cols) - available_columns
        
        # Special OR conditions
        if key == "C01_demographics":
            if not any(c in available_columns for c in ["gender", "age", "birth_date"]):
                missing_req.add("gender_or_age")
        elif key == "C03_geo_distribution":
            if not any(c in available_columns for c in ["customer_city", "region"]):
                missing_req.add("customer_city_or_region")

        missing_opt = set(mod.optional_cols) - available_columns

        results[key] = {
            "can_run": len(missing_req) == 0,
            "module": mod,
            "missing_required": list(missing_req),
            "missing_optional": list(missing_opt),
        }
    return results
