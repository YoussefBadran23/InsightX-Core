/**
 * Chart registry — maps analytics module_key → React component.
 *
 * `<ChartCard>` looks up the component here. Modules without an entry fall
 * back to `<EmptyChart>` so the dashboard never blanks out on unimplemented
 * modules.
 *
 * Adding a new chart:
 *   1. Build the component in `src/components/charts/<XnnName>.tsx`
 *   2. Import it here
 *   3. Add `<key>: <Component>` to the map below
 *
 * Components must accept `{ data: any, moduleKey: string }` props and fit
 * their own size inside the parent container (use `w-full h-full`).
 */

import { ComponentType } from "react";

// 2D bespoke charts with embedded headline cards
import { A01RevenueChart } from "./A01RevenueChart";
import { A11StatusDonut } from "./A11StatusDonut";
import { A15ForecastChart } from "./A15ForecastChart";

// 3D charts
import { A02RFM3DChart } from "./A02RFM3DChart";
import { A19Segmentation3DChart } from "./A19Segmentation3DChart";

// Batched chart files (grouped by chart_type)
import {
  A09TopProductsChart, A24BasketRecsChart, C02TopCustomersChart, P01ProductRankingChart,
} from "./BarHorizontalCharts";
import {
  A21ReturnRateChart, A25StockoutChart, P03BrandPerformanceChart,
  A26SentimentLTVChart, C06ActivityTimelineChart,
} from "./BarVerticalCharts";
import {
  C01DemographicsChart, C05SegmentBreakdownChart,
} from "./DonutCharts";
import {
  A04GrossMarginChart, A12DiscountChart, A18SentimentChart, C04NewVsReturningChart,
} from "./StackedBarCharts";
import {
  A08AOVTrendsChart, A13GrowthRatesChart, A23LifecycleChart, P04ProductSalesTrendChart,
} from "./MultiLineCharts";
import {
  A10LifetimeChart, A17CLVChart, A22SLAChart, P07PriceVolumeChart, A07ABCChart,
} from "./DistributionCharts";
// A14 promoted to its own file — gold-standard Decision-Chart v1 template
import { A14ChannelChart } from "./A14ChannelChart";
import { P02CategoryChart } from "./TreemapCharts";
import {
  A05CohortRetentionChart, P06ReturnHeatmapChart,
} from "./HeatmapCharts";
import {
  A20ChurnChart, P05StockHealthChart,
} from "./GaugeCharts";
import {
  A16AnomalyChart, A03MarketBasketChart, A06GeographicChart, C03GeoDistributionChart,
} from "./SpecializedCharts";

export interface ChartProps {
  data: any;
  moduleKey: string;
}

export const chartRegistry: Record<string, ComponentType<ChartProps>> = {
  // ── Series A — Transaction Analytics (26 modules) ──────────────────────
  A01_revenue_summary: A01RevenueChart,
  A02_rfm_scoring: A02RFM3DChart,
  A03_market_basket: A03MarketBasketChart,
  A04_gross_margin: A04GrossMarginChart,
  A05_cohort_retention: A05CohortRetentionChart,
  A06_geographic_revenue: A06GeographicChart,
  A07_abc_classification: A07ABCChart,
  A08_aov_trends: A08AOVTrendsChart,
  A09_top_n_products: A09TopProductsChart,
  A10_customer_lifetime: A10LifetimeChart,
  A11_order_status: A11StatusDonut,
  A12_discount_impact: A12DiscountChart,
  A13_growth_rates: A13GrowthRatesChart,
  A14_acquisition_channel: A14ChannelChart,
  A15_prophet_forecast: A15ForecastChart,
  A16_anomaly_detection: A16AnomalyChart,
  A17_clv_prediction: A17CLVChart,
  A18_sentiment_analysis: A18SentimentChart,
  A19_customer_segmentation: A19Segmentation3DChart,
  A20_churn_prediction: A20ChurnChart,
  A21_return_rate: A21ReturnRateChart,
  A22_fulfillment_sla: A22SLAChart,
  A23_product_lifecycle: A23LifecycleChart,
  A24_basket_recommendations: A24BasketRecsChart,
  A25_stockout_risk: A25StockoutChart,
  A26_sentiment_ltv: A26SentimentLTVChart,

  // ── Series C — Customer Analytics (6 modules) ──────────────────────────
  C01_demographics: C01DemographicsChart,
  C02_top_customers: C02TopCustomersChart,
  C03_geo_distribution: C03GeoDistributionChart,
  C04_new_vs_returning: C04NewVsReturningChart,
  C05_segment_breakdown: C05SegmentBreakdownChart,
  C06_activity_timeline: C06ActivityTimelineChart,

  // ── Series P — Product Analytics (7 modules) ───────────────────────────
  P01_product_ranking: P01ProductRankingChart,
  P02_category_performance: P02CategoryChart,
  P03_brand_performance: P03BrandPerformanceChart,
  P04_product_sales_trend: P04ProductSalesTrendChart,
  P05_stock_health: P05StockHealthChart,
  P06_return_heatmap: P06ReturnHeatmapChart,
  P07_price_volume: P07PriceVolumeChart,
};
