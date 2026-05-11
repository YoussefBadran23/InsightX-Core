'use client';

import { useEffect, useMemo, useState } from 'react';
import { DollarSign, Users, TrendingDown, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { kpiApi, analyticsApi } from '@/lib/api';
import { useUiStore } from '@/stores/uiStore';
import { t } from '@/lib/i18n';
import type { KpiSummary, KpiHistoryItem } from '@/types';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useRouter } from 'next/navigation';

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
  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [history, setHistory] = useState<KpiHistoryItem[]>([]);
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

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
  }, [router]);

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
          <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 shadow-sm">
            <div className="flex justify-between items-start">
              <p className="text-slate-500 dark:text-slate-400 text-sm font-medium leading-normal">{t('kpi_totalRevenue', language)}</p>
              <DollarSign className="text-primary w-6 h-6" />
            </div>
            <div className="flex items-baseline gap-3 mt-1">
              <p className="text-gray-900 dark:text-white tracking-tight text-3xl font-bold leading-tight">
                ${kpi ? (Number(kpi.total_revenue) / 1000).toFixed(1) + 'k' : '0.0k'}
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
          <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 shadow-sm">
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
          <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 shadow-sm">
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
          <div className="lg:col-span-2 rounded-xl bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 p-6 shadow-sm">
            <div className="flex flex-col gap-1 mb-6">
              <h3 className="text-gray-900 dark:text-white text-lg font-bold leading-normal">{t('chart_salesTrend', language)}</h3>
              <div className="flex gap-2 items-center">
                <p className="text-slate-500 text-sm">
                  {chartData.length > 0 ? `${chartData.length} ${t('chart_salesTrendDesc', language)}` : t('chart_noHistory', language)}
                </p>
                {kpi?.revenue_delta?.direction === 'up' && kpi.revenue_delta.change_pct !== null && (
                  <span className="text-emerald-500 text-sm font-medium">+{kpi.revenue_delta.change_pct}%</span>
                )}
              </div>
            </div>

            <div className="w-full h-[300px]">
              {chartData.length === 0 ? (
                <div className="w-full h-full flex items-center justify-center text-slate-400 text-sm">
                  {t('chart_noHistory', language)}
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 0, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#137fec" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#137fec" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} opacity={0.6} tickLine={false} axisLine={false} minTickGap={30} />
                    <YAxis
                      tick={{ fontSize: 11 }} opacity={0.6} tickLine={false} axisLine={false}
                      tickFormatter={(val) => `$${Math.round(val / 1000)}k`}
                    />
                    <Tooltip
                      formatter={(v: any, name: any) =>
                        name === 'revenue'
                          ? [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, t('kpi_totalRevenue', language)]
                          : [v, name]
                      }
                      contentStyle={{ borderRadius: 8 }}
                    />
                    <Area type="monotone" dataKey="revenue" stroke="#137fec" strokeWidth={3} fillOpacity={1} fill="url(#colorRevenue)" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Revenue by Region — real A06 */}
          <div className="rounded-xl bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 p-6 shadow-sm flex flex-col">
            <div className="flex flex-col gap-1 mb-6">
              <h3 className="text-gray-900 dark:text-white text-lg font-bold leading-normal">{t('chart_revenueByRegion', language)}</h3>
              <p className="text-slate-500 text-xs">
                {regions.length > 0
                  ? `${t('chart_topRegions', language)}: ${regions.length}`
                  : t('chart_noRegional', language)}
              </p>
            </div>

            <div className="flex-1 flex items-end justify-between px-2 gap-3 min-h-[200px]">
              {regions.length === 0 ? (
                <div className="w-full flex items-center justify-center text-slate-400 text-xs">
                  {t('chart_noRegional', language)}
                </div>
              ) : (
                regions.map((r) => {
                  const heightPct = maxRegionRev > 0 ? Math.max(8, (Number(r.revenue) / maxRegionRev) * 100) : 8;
                  return (
                    <div key={r.region} className="flex flex-col items-center gap-2 w-full">
                      <div className="w-full rounded-t-sm bg-gray-100 dark:bg-slate-700/30 relative h-48 flex items-end overflow-hidden group">
                        <div
                          className="w-full bg-primary group-hover:bg-primary-hover transition-all duration-500 rounded-t-sm relative"
                          style={{ height: `${heightPct}%` }}
                          title={`$${Math.round(Number(r.revenue)).toLocaleString()} (${r.pct}%)`}
                        />
                      </div>
                      <p className="text-slate-500 text-xs font-bold truncate max-w-full" title={r.region}>
                        {r.region.length > 8 ? r.region.slice(0, 7) + '…' : r.region}
                      </p>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
