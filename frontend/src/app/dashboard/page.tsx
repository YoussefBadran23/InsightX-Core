'use client';

import { useEffect, useMemo, useState } from 'react';
import { DollarSign, Users, TrendingDown, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { kpiApi, analyticsApi, jobsApi } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { useJobStore } from '@/stores/jobStore';
import { useDashboardStore } from '@/stores/dashboardStore';
import { t } from '@/lib/i18n';
import { formatMoney } from '@/lib/format';
import type { KpiSummary, KpiHistoryItem, UploadJob } from '@/types';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useRouter } from 'next/navigation';
import { LayoutDashboard } from 'lucide-react';
import Link from 'next/link';
import { ChartCard } from '@/components/charts/ChartCard';
import { InsightCard } from '@/components/charts/foundation/InsightCard';
import { InsightTooltip } from '@/components/charts/foundation/InsightTooltip';
import { useChartTheme } from '@/components/charts/chartHelpers';

interface RegionRow {
  region: string;
  revenue: number;
  orders: number;
  customers: number;
  pct: number;
  rank: number;
}

export default function DashboardHome() {
  const { language } = useUiStore();
  const user = useAuthStore((s) => s.user);
  const currency = user?.preferred_currency || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const setSourceCurrency = useJobStore((s) => s.setSourceCurrency);
  const theme = useChartTheme();
  // The committed (Save Layout) widgets — drive the "My Custom Charts" strip
  // at the bottom of the home page. Falls back to the working set if the
  // user hasn't explicitly saved yet (so a fresh first-time visitor still
  // sees something instead of a "Customize your dashboard" empty state).
  const savedWidgets = useDashboardStore((s) =>
    s.savedWidgets.length > 0 ? s.savedWidgets : s.widgets,
  );
  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [history, setHistory] = useState<KpiHistoryItem[]>([]);
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [latestJobId, setLatestJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Need the latest job id for widget chart data fetches.
  useEffect(() => {
    jobsApi.list(1, 1)
      .then((res) => {
        const latest = (res.data?.items?.[0] || null) as UploadJob | null;
        if (latest?.id) setLatestJobId(latest.id);
      })
      .catch(() => { /* widgets simply render empty states */ });
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [kpiRes, historyRes] = await Promise.all([
          kpiApi.summary(),
          kpiApi.history(30).catch(() => ({ data: { days: 30, items: [] } })),
        ]);
        if (cancelled) return;

        const k = kpiRes.data as KpiSummary;
        if (k && k.total_revenue === 0 && k.active_customers === 0) {
          router.push('/dashboard/upload');
          return;
        }
        setKpi(k);
        // Reflect the latest job's source currency into the global store so
        // sibling pages format money against the same `from` currency.
        if (k?.source_currency) setSourceCurrency(k.source_currency);
        setHistory((historyRes.data as any)?.items || []);

        try {
          const geoRes = await analyticsApi.get('geographic');
          const byRegion = (geoRes.data?.result_json?.by_region || []) as RegionRow[];
          if (!cancelled) setRegions(byRegion.slice(0, 5));
        } catch {
          /* A06 not available — leave regions empty */
        }
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [router, setSourceCurrency]);

  const chartData = useMemo(
    () => history.map((h) => ({
      date: h.snapshot_date,
      revenue: Number(h.total_revenue),
      orders: Number(h.total_orders),
    })),
    [history],
  );

  const maxRegionRev = useMemo(
    () => regions.length === 0 ? 0 : Math.max(...regions.map((r) => Number(r.revenue) || 0)),
    [regions],
  );

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-8">
      <div className="mx-auto max-w-7xl flex flex-col gap-6 animate-fade-in">
        {/* KPI Cards Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Revenue */}
          <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-surface-card border border-slate-200 dark:border-white/10 shadow-sm">
            <div className="flex justify-between items-start">
              <p className="text-slate-500 dark:text-slate-400 text-sm font-medium leading-normal">{t('kpi_totalRevenue', language)}</p>
              <DollarSign className="text-primary w-6 h-6" />
            </div>
            <div className="flex items-baseline gap-3 mt-1">
              <p className="text-gray-900 dark:text-white tracking-tight text-3xl font-bold leading-tight">
                {formatMoney(kpi?.total_revenue, currency, { from: sourceCurrency })}
              </p>
              {kpi?.revenue_delta && kpi.revenue_delta.change_pct !== null && (
                <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-sm font-medium ${
                  kpi.revenue_delta.direction === 'up'
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-500'
                    : 'bg-red-500/10 text-red-600 dark:text-red-500'
                }`}>
                  {kpi.revenue_delta.direction === 'up'
                    ? <ArrowUpRight className="w-4 h-4" />
                    : <ArrowDownRight className="w-4 h-4" />}
                  <span>{Math.abs(kpi.revenue_delta.change_pct)}%</span>
                </div>
              )}
            </div>
          </div>

          {/* Customers */}
          <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-surface-card border border-slate-200 dark:border-white/10 shadow-sm">
            <div className="flex justify-between items-start">
              <p className="text-slate-500 dark:text-slate-400 text-sm font-medium leading-normal">{t('kpi_activeCustomers', language)}</p>
              <Users className="text-primary w-6 h-6" />
            </div>
            <div className="flex items-baseline gap-3 mt-1">
              <p className="text-gray-900 dark:text-white tracking-tight text-3xl font-bold leading-tight">
                {kpi?.active_customers?.toLocaleString() || 0}
              </p>
              {kpi?.customers_delta && kpi.customers_delta.change_pct !== null && (
                <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-sm font-medium ${
                  kpi.customers_delta.direction === 'up'
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-500'
                    : 'bg-red-500/10 text-red-600 dark:text-red-500'
                }`}>
                  {kpi.customers_delta.direction === 'up'
                    ? <ArrowUpRight className="w-4 h-4" />
                    : <ArrowDownRight className="w-4 h-4" />}
                  <span>{Math.abs(kpi.customers_delta.change_pct)}%</span>
                </div>
              )}
            </div>
          </div>

          {/* Churn */}
          <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-surface-card border border-slate-200 dark:border-white/10 shadow-sm">
            <div className="flex justify-between items-start">
              <p className="text-slate-500 dark:text-slate-400 text-sm font-medium leading-normal">{t('kpi_churnRate', language)}</p>
              <TrendingDown className="text-primary w-6 h-6" />
            </div>
            <div className="flex items-baseline gap-3 mt-1">
              <p className="text-gray-900 dark:text-white tracking-tight text-3xl font-bold leading-tight">
                {kpi ? `${Number(kpi.churn_rate).toFixed(1)}%` : '0%'}
              </p>
            </div>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-slide-up">
          {/* Sales Trend — real /kpi/history */}
          <div className="lg:col-span-2 min-h-[350px]">
            <InsightCard 
              title={t('chart_salesTrend', language)} 
              subtitle={chartData.length > 0 ? `${chartData.length} ${t('chart_salesTrendDesc', language)}` : t('chart_noHistory', language)}
              headerRight={
                kpi?.revenue_delta?.direction === 'up' && kpi.revenue_delta.change_pct !== null && (
                  <span className="text-emerald-500 text-sm font-bold bg-emerald-500/10 px-2 py-1 rounded-md">+{kpi.revenue_delta.change_pct}%</span>
                )
              }
            >
              <div className="w-full flex-1">
                {chartData.length === 0 ? (
                  <div className="w-full h-full flex items-center justify-center text-slate-400 text-sm">
                    {t('chart_noHistory', language)}
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 0, left: -10, bottom: 0 }}>
                      <defs>
                        {/* Brand-tinted vertical fade — saturated at the line,
                            transparent at the axis. Anchors the data without
                            painting a heavy block over the card. */}
                        <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={theme.semantic.brand} stopOpacity={0.42} />
                          <stop offset="55%" stopColor={theme.semantic.brand} stopOpacity={0.16} />
                          <stop offset="95%" stopColor={theme.semantic.brand} stopOpacity={0} />
                        </linearGradient>
                        {/* Premium glow filter — the entire line gets a soft
                            halo so it reads as "alive" against the card. The
                            filter id is page-scoped so it doesn't collide with
                            chart-card glow filters elsewhere on the dashboard. */}
                        <filter id="dashboard-glow" x="-20%" y="-50%" width="140%" height="200%">
                          <feGaussianBlur stdDeviation={theme.isDark ? 3.5 : 2.2} result="blur" />
                          <feComposite in="SourceGraphic" in2="blur" operator="over" />
                        </filter>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke={theme.gridStroke}
                        strokeOpacity={0.7}
                      />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 11, fill: theme.text.muted }}
                        tickLine={false}
                        axisLine={false}
                        minTickGap={30}
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: theme.text.muted }}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(val) => formatMoney(val, currency, { from: sourceCurrency })}
                      />
                      <Tooltip content={<InsightTooltip currency={currency} sourceCurrency={sourceCurrency} />} />
                      <Area
                        type="monotone"
                        dataKey="revenue"
                        name="Revenue"
                        stroke={theme.semantic.brand}
                        strokeWidth={2.75}
                        fillOpacity={1}
                        fill="url(#colorRevenue)"
                        filter="url(#dashboard-glow)"
                        activeDot={{
                          r: 6,
                          strokeWidth: 2,
                          stroke: theme.surface,
                          fill: theme.semantic.brand,
                          filter: 'url(#dashboard-glow)',
                        }}
                        isAnimationActive={true}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </InsightCard>
          </div>

          {/* Revenue by Region — real A06 */}
          <div className="min-h-[350px]">
            <InsightCard
              title={t('chart_revenueByRegion', language)}
              subtitle={regions.length > 0 ? `${t('chart_topRegions', language)}: ${regions.length}` : t('chart_noRegional', language)}
            >
              <div className="flex-1 flex items-end justify-between gap-3 h-full pb-2">
                {regions.length === 0 ? (
                  <div
                    className="w-full h-full flex items-center justify-center text-sm"
                    style={{ color: theme.text.muted }}
                  >
                    {t('chart_noRegional', language)}
                  </div>
                ) : (
                  regions.map((r, idx) => {
                    const heightPct = maxRegionRev > 0 ? Math.max(12, (Number(r.revenue) / maxRegionRev) * 100) : 12;
                    const isTop = idx === 0;
                    const brand = theme.semantic.brand;
                    return (
                      <div
                        key={r.region}
                        className="flex flex-col items-center gap-2 w-full h-full justify-end group cursor-pointer"
                        title={`${formatMoney(r.revenue, currency, { exact: true, decimals: 0, from: sourceCurrency })} (${r.pct}%)`}
                      >
                        {/* Rank chip — sits above the bar, brand-tinted */}
                        <span
                          className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                          style={{
                            color: brand,
                            background: theme.semanticSoft.brand,
                            border: `1px solid ${brand}33`,
                          }}
                        >
                          #{r.rank ?? idx + 1}
                        </span>

                        {/* Bar track + animated fill */}
                        <div
                          className="w-full rounded-t-lg relative flex items-end overflow-hidden flex-1 max-h-[80%]"
                          style={{ background: theme.surfaceMuted }}
                        >
                          {/* Inner ring — glassmorphic accent on the track */}
                          <div
                            className="absolute inset-0 rounded-t-lg pointer-events-none"
                            style={{
                              boxShadow: theme.isDark
                                ? 'inset 0 1px 0 rgba(255,255,255,0.05)'
                                : 'inset 0 1px 0 rgba(15,23,42,0.04)',
                            }}
                          />
                          {/* The bar itself */}
                          <div
                            className="w-full rounded-t-lg relative transition-all duration-500 group-hover:-translate-y-0.5"
                            style={{
                              height: `${heightPct}%`,
                              background: `linear-gradient(to top, ${brand}cc 0%, ${brand} 60%, ${brand}f5 100%)`,
                              boxShadow: isTop
                                ? `0 -2px 18px ${brand}66, 0 0 24px ${brand}33`
                                : `0 -2px 12px ${brand}40`,
                            }}
                          >
                            {/* Glassy top highlight — runs across the bar's
                                top edge to give the surface a polished glint */}
                            <div
                              className="absolute inset-x-0 top-0 h-1.5 rounded-t-lg pointer-events-none"
                              style={{
                                background: 'linear-gradient(to bottom, rgba(255,255,255,0.55), rgba(255,255,255,0))',
                              }}
                            />
                            {/* Hover-only revenue label inside the bar */}
                            <span
                              className="absolute inset-x-0 -top-5 text-[10px] font-bold text-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 whitespace-nowrap"
                              style={{ color: brand }}
                            >
                              {formatMoney(r.revenue, currency, { from: sourceCurrency })}
                            </span>
                          </div>
                        </div>

                        {/* Region label */}
                        <p
                          className="text-[11px] font-bold truncate max-w-[80px] text-center transition-colors"
                          style={{ color: isTop ? brand : theme.text.body }}
                          title={r.region}
                        >
                          {r.region.length > 8 ? r.region.slice(0, 7) + '…' : r.region}
                        </p>
                      </div>
                    );
                  })
                )}
              </div>
            </InsightCard>
          </div>
        </div>

        {/* ── User-customized widget strip ────────────────────────────────
            Renders the widgets the user committed via Save Layout. We show
            the first 6 to keep the home page focused; full grid lives on
            /dashboard/analytics. If the user has never customized, this
            section quietly disappears (savedWidgets falls back to the seeded
            default which is 39 charts — so we cap display at 6 either way). */}
        {savedWidgets.length > 0 && (
          <div className="flex flex-col gap-4 animate-slide-up">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <LayoutDashboard className="w-5 h-5 text-primary" />
                <h3 className="text-gray-900 dark:text-white text-lg font-bold leading-normal">
                  {language === 'ar' ? 'لوحتي المخصصة' : 'My Custom Charts'}{/* TODO: add i18n key */}
                </h3>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                  {savedWidgets.length}
                </span>
              </div>
              <Link
                href="/dashboard/analytics"
                className="text-xs font-medium text-primary hover:underline"
              >
                {language === 'ar' ? 'عرض الكل' : 'View all'} →
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {savedWidgets.slice(0, 6).map((w) => (
                <div key={w.id} className="min-h-[280px]">
                  <ChartCard widgetId={w.id} moduleKey={w.module_key} jobId={latestJobId} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
