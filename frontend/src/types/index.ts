// All TypeScript types for the InsightX frontend

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  preferred_language: 'en' | 'ar' | null;
  preferred_theme: 'light' | 'dark' | null;
}

export interface UploadJob {
  id: string;
  original_filename: string | null;
  status: 'pending' | 'mapping' | 'validating' | 'inserting' | 'analyzing' | 'completed' | 'failed';
  rows_total: number | null;
  rows_processed: number;
  rows_failed: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ModuleStatus {
  module_key: string;
  module_name: string;
  module_name_ar: string;
  description: string;
  can_run: boolean;
  queue: string;
  run_status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  missing_required_columns: string[] | null;
  missing_optional_columns: string[] | null;
  error_message: string | null;
}

export interface JobDetail extends UploadJob {
  modules: ModuleStatus[];
}

export interface KpiDelta {
  current: number;
  previous: number | null;
  change_pct: number | null;
  direction: 'up' | 'down' | 'flat';
}

export interface KpiSummary {
  snapshot_date: string;
  total_revenue: number;
  active_customers: number;
  new_customers: number;
  total_orders: number;
  avg_order_value: number;
  churn_rate: number;
  revenue_na: number;
  revenue_eu: number;
  revenue_apac: number;
  revenue_latam: number;
  revenue_delta: KpiDelta | null;
  customers_delta: KpiDelta | null;
  orders_delta: KpiDelta | null;
  aov_delta: KpiDelta | null;
}

export interface KpiHistoryItem {
  snapshot_date: string;
  total_revenue: number;
  active_customers: number;
  total_orders: number;
  avg_order_value: number;
}

export interface KpiHistory {
  days: number;
  items: KpiHistoryItem[];
}

export interface Customer {
  id: string;
  external_id: string | null;
  email: string;
  full_name: string | null;
  country: string | null;
  region: string | null;
  first_purchase_date: string | null;
  total_orders: number;
  lifetime_value: number;
  ai_segment: 'vip_champion' | 'loyalist' | 'at_risk' | 'new_potential' | 'undetermined' | null;
  churn_risk_score: number | null;
  clv_predicted: number | null;
  rfm_segment: string | null;
  rfm_score: string | null;
  last_active_at: string | null;
  is_active: boolean;
}

export interface CustomerDetail extends Customer {
  arr: number;
  engagement_score: number;
  cohort_month: string | null;
  age_group: string | null;
  gender: string | null;
  country_code: string | null;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  category: string;
  unit_price: number;
  cost_price: number | null;
  stock_qty: number;
  low_stock_threshold: number;
  abc_tier: 'A' | 'B' | 'C' | null;
  return_rate: number | null;
  total_revenue: number;
  total_units_sold: number;
  is_active: boolean;
  is_low_stock: boolean;
  gross_margin_pct: number | null;
}

export interface ForecastPoint {
  ds: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
  is_historical: boolean;
}

export interface ForecastSummary {
  avg_daily_forecast: number;
  total_forecast_revenue: number;
  lower_bound_total: number;
  upper_bound_total: number;
}

export interface Forecast {
  job_id: string;
  method: string;
  historical: ForecastPoint[];
  forecast: ForecastPoint[];
  forecast_periods: number;
  total_historical_days: number;
  forecast_summary: ForecastSummary;
  computed_at: string;
}

export interface Insight {
  id: string;
  job_id: string | null;
  title: string | null;
  body: string;
  insight_type: string | null;
  priority: number | null;
  created_at: string;
}

export interface AnalyticsResult {
  analysis_type: string;
  upload_job_id: string | null;
  result_json: Record<string, unknown>;
  computed_at: string;
  is_stale: boolean;
  duration_ms: number | null;
}

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  items: T[];
}

export type CustomerList = PaginatedResponse<Customer>;
export type ProductList  = PaginatedResponse<Product>;
export type JobList      = PaginatedResponse<UploadJob>;

// Segment display config
export const SEGMENT_CONFIG = {
  vip_champion: { label: 'VIP Champion', class: 'badge-vip',      icon: '👑' },
  loyalist:     { label: 'Loyalist',     class: 'badge-loyalist', icon: '💎' },
  at_risk:      { label: 'At Risk',      class: 'badge-at-risk',  icon: '⚠️' },
  new_potential:{ label: 'New Potential',class: 'badge-new',      icon: '🌱' },
  undetermined: { label: 'Unknown',      class: 'badge-pending',  icon: '?' },
} as const;

export const ABC_CONFIG = {
  A: { label: 'Tier A', class: 'badge-abc-a' },
  B: { label: 'Tier B', class: 'badge-abc-b' },
  C: { label: 'Tier C', class: 'badge-abc-c' },
} as const;

export const JOB_STATUS_CONFIG = {
  pending:    { label: 'Pending',    class: 'badge-pending',    stage: 0 },
  mapping:    { label: 'Mapping',    class: 'badge-processing', stage: 1 },
  validating: { label: 'Validating', class: 'badge-processing', stage: 2 },
  inserting:  { label: 'Inserting',  class: 'badge-processing', stage: 3 },
  analyzing:  { label: 'Analyzing',  class: 'badge-processing', stage: 4 },
  completed:  { label: 'Completed',  class: 'badge-completed',  stage: 5 },
  failed:     { label: 'Failed',     class: 'badge-failed',     stage: -1 },
} as const;
