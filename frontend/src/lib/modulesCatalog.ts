/**
 * Static catalog of all 39 InsightX analytics modules.
 *
 * Mirrors `worker/schema.py` MODULES. Kept in sync manually (the backend ships
 * the authoritative schema; this catalog only adds chart-type hints + EN/AR
 * labels for the dashboard customizer).
 *
 * Each module's `chart_type` drives which component the registry renders:
 *   - 2D types are Recharts-backed (fast, plays nice with grid resizing)
 *   - "3d_*" types use react-three-fiber (used sparingly — only where 3D
 *     genuinely adds clarity, e.g. RFM cube, segmentation clusters)
 */

export type ChartType =
  | "area_line"      // time-series single metric (revenue, AOV)
  | "multi_line"     // multiple lines (per-region, per-cohort)
  | "bar_horizontal" // top-N rankings
  | "bar_vertical"   // categorical comparison
  | "stacked_bar"    // composition over time
  | "donut"          // distribution (status, segments)
  | "pareto"         // bar + cumulative line (ABC)
  | "heatmap"        // 2D matrix (cohort retention, returns)
  | "scatter"        // correlation (sentiment-LTV, price-volume)
  | "forecast_band"  // line + confidence band (Prophet)
  | "anomaly_scatter"// scatter with flagged outliers (A16)
  | "treemap"        // hierarchical share (categories, channels)
  | "gauge"          // single KPI dial (risk scores, churn)
  | "histogram"      // distribution buckets (LTV, lifespan)
  | "network"        // force-directed graph (market basket)
  | "map_choropleth" // geographic
  | "3d_scatter"     // RFM cube, segmentation
  | "3d_surface"     // cohort retention 3D
  | "kpi_cards";     // headline numbers only

export interface ModuleMeta {
  key: string;
  name_en: string;
  name_ar: string;
  series: "A" | "C" | "P";       // Transaction / Customer / Product
  required_cols: string[];
  chart_type: ChartType;
  default_w: number;             // grid width (1..12)
  default_h: number;             // grid height (rows)
  /** Short human-readable description, surfaced in chart card empty states.
   *  Kept in EN only — the chart card's data states are technical and
   *  don't currently need to be localised. */
  description: string;
}

export const MODULES_CATALOG: ModuleMeta[] = [
  // ── Series A — Transaction Analytics (26) ─────────────────────────────────
  { key: "A01_revenue_summary",   name_en: "Revenue Summary",                name_ar: "ملخص الإيرادات",          series: "A", required_cols: ["order_date", "total_amount"],                   chart_type: "area_line",       default_w: 8, default_h: 4, description: "Headline revenue with daily/weekly/monthly trend." },
  { key: "A02_rfm_scoring",       name_en: "RFM Scoring",                    name_ar: "تحليل RFM",               series: "A", required_cols: ["customer_id", "order_date", "total_amount"],    chart_type: "3d_scatter",      default_w: 6, default_h: 6, description: "Recency × Frequency × Monetary cube. Drag to explore." },
  { key: "A03_market_basket",     name_en: "Market Basket Analysis",         name_ar: "تحليل سلة المشتريات",       series: "A", required_cols: ["order_id", "product_id"],                       chart_type: "network",         default_w: 6, default_h: 5, description: "Products bought together — edges weighted by lift." },
  { key: "A04_gross_margin",      name_en: "Gross Margin Analysis",          name_ar: "تحليل هامش الربح",         series: "A", required_cols: ["cost_amount", "total_amount"],                  chart_type: "stacked_bar",     default_w: 6, default_h: 4, description: "Cost vs profit margin per period." },
  { key: "A05_cohort_retention",  name_en: "Cohort Retention",               name_ar: "تحليل الاحتفاظ بالعملاء",   series: "A", required_cols: ["customer_id", "order_date"],                    chart_type: "heatmap",         default_w: 8, default_h: 5, description: "% of each acquisition cohort still active N months later." },
  { key: "A06_geographic_revenue",name_en: "Geographic Revenue",             name_ar: "الإيرادات الجغرافية",      series: "A", required_cols: ["region", "total_amount"],                        chart_type: "map_choropleth",  default_w: 6, default_h: 5, description: "Revenue ranked by country, region, or city." },
  { key: "A07_abc_classification",name_en: "ABC Tier Classification",        name_ar: "تصنيف ABC",                series: "A", required_cols: ["product_id", "total_amount"],                    chart_type: "pareto",          default_w: 6, default_h: 4, description: "Pareto curve — products tagged A/B/C by revenue share." },
  { key: "A08_aov_trends",        name_en: "Average Order Value Trends",     name_ar: "اتجاهات متوسط قيمة الطلب",  series: "A", required_cols: ["order_date", "total_amount"],                   chart_type: "multi_line",      default_w: 6, default_h: 4, description: "Monthly AOV with seasonality patterns." },
  { key: "A09_top_n_products",    name_en: "Top N Products",                 name_ar: "أفضل المنتجات",           series: "A", required_cols: ["product_id", "total_amount"],                    chart_type: "bar_horizontal",  default_w: 4, default_h: 5, description: "Top products ranked by revenue contribution." },
  { key: "A10_customer_lifetime", name_en: "Customer Lifetime Stats",        name_ar: "إحصائيات عمر العميل",      series: "A", required_cols: ["customer_id", "total_amount"],                  chart_type: "histogram",       default_w: 6, default_h: 4, description: "LTV spend distribution across the customer base." },
  { key: "A11_order_status",      name_en: "Order Status Distribution",      name_ar: "توزيع حالة الطلبات",       series: "A", required_cols: ["status"],                                       chart_type: "donut",           default_w: 4, default_h: 4, description: "Success vs in-progress vs failure mix, with success rate." },
  { key: "A12_discount_impact",   name_en: "Discount Impact Analysis",       name_ar: "تحليل تأثير الخصومات",     series: "A", required_cols: ["discount_amount", "total_amount"],              chart_type: "stacked_bar",     default_w: 6, default_h: 4, description: "Discount $ vs net revenue per month." },
  { key: "A13_growth_rates",      name_en: "Period Growth Rates",            name_ar: "معدلات النمو",            series: "A", required_cols: ["order_date", "total_amount"],                    chart_type: "multi_line",      default_w: 6, default_h: 4, description: "Monthly revenue + 3-month rolling average." },
  { key: "A14_acquisition_channel",name_en:"Acquisition by Channel",         name_ar: "اكتساب العملاء حسب القناة", series: "A", required_cols: ["acquisition_channel", "customer_id"],          chart_type: "treemap",         default_w: 6, default_h: 4, description: "Revenue share by acquisition channel." },
  { key: "A15_prophet_forecast",  name_en: "Revenue Forecasting",            name_ar: "التنبؤ بالإيرادات",        series: "A", required_cols: ["order_date", "total_amount"],                   chart_type: "forecast_band",   default_w: 8, default_h: 4, description: "180-day revenue forecast with 80% confidence band." },
  { key: "A16_anomaly_detection", name_en: "Anomaly Detection",              name_ar: "كشف الشذوذ",              series: "A", required_cols: ["order_date", "total_amount"],                   chart_type: "anomaly_scatter", default_w: 8, default_h: 4, description: "Days flagged as unusual spikes or drops." },
  { key: "A17_clv_prediction",    name_en: "CLV Prediction",                 name_ar: "توقع قيمة العميل",         series: "A", required_cols: ["customer_id", "order_date", "total_amount"],    chart_type: "histogram",       default_w: 6, default_h: 4, description: "365-day predicted CLV distribution." },
  { key: "A18_sentiment_analysis",name_en: "Sentiment Analysis",             name_ar: "تحليل المشاعر",           series: "A", required_cols: ["comment_text"],                                  chart_type: "stacked_bar",     default_w: 6, default_h: 4, description: "Positive/neutral/negative comment mix per category." },
  { key: "A19_customer_segmentation",name_en:"Customer Segmentation",        name_ar: "تقسيم العملاء",           series: "A", required_cols: ["customer_id", "order_date", "total_amount"],    chart_type: "3d_scatter",      default_w: 6, default_h: 6, description: "K-Means clusters in R×F×M space." },
  { key: "A20_churn_prediction",  name_en: "Churn Risk Prediction",          name_ar: "توقع مخاطر فقدان العملاء",  series: "A", required_cols: ["customer_id", "order_date", "total_amount"],   chart_type: "gauge",           default_w: 4, default_h: 4, description: "Average churn risk across the customer base." },
  { key: "A21_return_rate",       name_en: "Return Rate Analysis",           name_ar: "تحليل معدل الإرجاع",       series: "A", required_cols: ["product_id", "return_flag"],                   chart_type: "bar_vertical",    default_w: 6, default_h: 4, description: "Products with the highest return rates." },
  { key: "A22_fulfillment_sla",   name_en: "Fulfillment SLA Analysis",       name_ar: "تحليل مستوى خدمة التوصيل", series: "A", required_cols: ["delivery_days"],                               chart_type: "histogram",       default_w: 6, default_h: 4, description: "Delivery-day distribution + SLA compliance." },
  { key: "A23_product_lifecycle", name_en: "Product Life-Cycle Decay",       name_ar: "دورة حياة المنتج",         series: "A", required_cols: ["order_date", "product_id", "total_amount"],   chart_type: "multi_line",      default_w: 6, default_h: 4, description: "Top products and which life-cycle stage they sit in." },
  { key: "A24_basket_recommendations",name_en:"Basket Recommendations",       name_ar: "توصيات سلة المشتريات",     series: "A", required_cols: ["order_id", "product_id", "quantity"],         chart_type: "bar_horizontal",  default_w: 6, default_h: 5, description: "If you sold X, recommend Y — ranked by lift." },
  { key: "A25_stockout_risk",     name_en: "Stock-Out Risk",                 name_ar: "مخاطر نفاد المخزون",       series: "A", required_cols: ["product_id", "quantity", "stock_qty"],         chart_type: "bar_vertical",    default_w: 6, default_h: 4, description: "Products predicted to run out soonest." },
  { key: "A26_sentiment_ltv",     name_en: "Sentiment vs LTV",               name_ar: "ارتباط المشاعر بقيمة العميل",series:"A", required_cols: ["comment_text", "customer_id", "total_amount"],  chart_type: "bar_vertical",    default_w: 6, default_h: 4, description: "Average LTV per sentiment bucket — happy spenders vs unhappy." },

  // ── Series C — Customer Analytics (6) ─────────────────────────────────────
  { key: "C01_demographics",      name_en: "Customer Demographics",          name_ar: "التركيبة السكانية للعملاء", series: "C", required_cols: [],                                              chart_type: "donut",           default_w: 4, default_h: 4, description: "Age + gender distribution across customers." },
  { key: "C02_top_customers",     name_en: "Top Customers by Revenue",       name_ar: "أفضل العملاء حسب الإيرادات",series: "C", required_cols: ["customer_id", "total_amount"],                 chart_type: "bar_horizontal",  default_w: 4, default_h: 5, description: "Leaderboard of biggest spenders." },
  { key: "C03_geo_distribution",  name_en: "Customer Geographic Distribution",name_ar:"التوزيع الجغرافي للعملاء",  series: "C", required_cols: ["customer_id"],                                chart_type: "map_choropleth",  default_w: 6, default_h: 5, description: "Where your customers live, by region/city." },
  { key: "C04_new_vs_returning",  name_en: "New vs Returning Customers",     name_ar: "العملاء الجدد مقابل العائدين",series:"C",required_cols:["customer_id", "order_date"],                   chart_type: "stacked_bar",     default_w: 6, default_h: 4, description: "Monthly mix of new vs returning customer orders." },
  { key: "C05_segment_breakdown", name_en: "Customer Segment Breakdown",     name_ar: "تقسيم قطاعات العملاء",     series: "C", required_cols: ["customer_id", "customer_segment"],             chart_type: "donut",           default_w: 4, default_h: 4, description: "Customer count per declared segment." },
  { key: "C06_activity_timeline", name_en: "Customer Activity Timeline",     name_ar: "الجدول الزمني لنشاط العميل",series: "C", required_cols: ["customer_id", "order_date", "total_amount"], chart_type: "bar_vertical",    default_w: 8, default_h: 4, description: "How many orders customers typically place." },

  // ── Series P — Product Analytics (7) ──────────────────────────────────────
  { key: "P01_product_ranking",   name_en: "Product Revenue Ranking",        name_ar: "تصنيف إيرادات المنتجات",   series: "P", required_cols: ["product_id", "total_amount"],                  chart_type: "bar_horizontal",  default_w: 4, default_h: 5, description: "Top products by revenue." },
  { key: "P02_category_performance",name_en:"Category Performance",          name_ar: "أداء الفئة",              series: "P", required_cols: ["category", "total_amount"],                    chart_type: "treemap",         default_w: 6, default_h: 5, description: "Revenue share by product category." },
  { key: "P03_brand_performance", name_en: "Brand Performance",              name_ar: "أداء العلامة التجارية",    series: "P", required_cols: ["brand", "total_amount"],                       chart_type: "bar_vertical",    default_w: 6, default_h: 4, description: "Revenue by brand." },
  { key: "P04_product_sales_trend",name_en:"Product Sales Trend",            name_ar: "اتجاه مبيعات المنتجات",    series: "P", required_cols: ["order_date", "product_id", "total_amount"],   chart_type: "multi_line",      default_w: 6, default_h: 4, description: "Time-series sales for the top 5 products." },
  { key: "P05_stock_health",      name_en: "Stock Health Dashboard",         name_ar: "لوحة صحة المخزون",         series: "P", required_cols: ["product_id", "stock_qty"],                     chart_type: "gauge",           default_w: 4, default_h: 4, description: "Inventory health score (low → out-of-stock alert)." },
  { key: "P06_return_heatmap",    name_en: "Product Return Heatmap",         name_ar: "خريطة حرارية لإرجاع المنتجات",series:"P", required_cols: ["product_id", "return_flag"],                 chart_type: "heatmap",         default_w: 6, default_h: 5, description: "Return rates by category × month." },
  { key: "P07_price_volume",      name_en: "Price vs Volume Analysis",       name_ar: "تحليل السعر مقابل الحجم",   series: "P", required_cols: ["product_id", "quantity", "unit_price"],       chart_type: "scatter",         default_w: 6, default_h: 5, description: "Price-sensitivity scatter (unit price vs units sold)." },
];

export const MODULES_BY_KEY: Record<string, ModuleMeta> = Object.fromEntries(
  MODULES_CATALOG.map((m) => [m.key, m]),
);

export const MODULES_BY_SERIES: Record<"A" | "C" | "P", ModuleMeta[]> = {
  A: MODULES_CATALOG.filter((m) => m.series === "A"),
  C: MODULES_CATALOG.filter((m) => m.series === "C"),
  P: MODULES_CATALOG.filter((m) => m.series === "P"),
};

export const SERIES_LABELS: Record<"A" | "C" | "P", { en: string; ar: string }> = {
  A: { en: "Transaction Analytics",  ar: "تحليلات المعاملات" },
  C: { en: "Customer Analytics",     ar: "تحليلات العملاء" },
  P: { en: "Product Analytics",      ar: "تحليلات المنتجات" },
};
