'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader2, AlertCircle, Award, ShieldCheck, AlertOctagon, Sparkles, Target } from 'lucide-react';
import { analyticsApi } from '@/lib/api';
import { useUiStore } from '@/stores/uiStore';
import { t, tp } from '@/lib/i18n';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface SegmentRow {
  segment: string;
  count: number;
  pct: number;
  revenue: number;
  rev_pct: number;
  avg_monetary: number;
}

interface TopCustomer {
  customer_id: string;
  recency_days: number;
  frequency: number;
  monetary: number;
  R: number;
  F: number;
  M: number;
  segment: string;
}

interface RfmResult {
  summary: {
    n_customers: number;
    snapshot_date: string | null;
    total_revenue: number;
    avg_recency: number;
    avg_frequency: number;
    avg_monetary: number;
  };
  segments: SegmentRow[];
  top_customers: TopCustomer[];
}

// Segment → visual config
const SEGMENT_STYLES: Record<string, { color: string; icon: any; family: 'champion' | 'loyal' | 'risk' | 'new' }> = {
  Champions:           { color: '#f59e0b', icon: Award,       family: 'champion' },
  'Loyal Customers':   { color: '#137fec', icon: ShieldCheck, family: 'loyal'    },
  'Potential Loyalists': { color: '#0ea5e9', icon: ShieldCheck, family: 'loyal'    },
  'New Customers':     { color: '#10b981', icon: Sparkles,    family: 'new'      },
  Promising:           { color: '#22c55e', icon: Sparkles,    family: 'new'      },
  'Need Attention':    { color: '#a78bfa', icon: ShieldCheck, family: 'loyal'    },
  'About to Sleep':    { color: '#fb923c', icon: AlertOctagon,family: 'risk'     },
  'At Risk':           { color: '#ef4444', icon: AlertOctagon,family: 'risk'     },
  'Cannot Lose Them':  { color: '#dc2626', icon: AlertOctagon,family: 'risk'     },
  Hibernating:         { color: '#94a3b8', icon: AlertOctagon,family: 'risk'     },
  Lost:                { color: '#64748b', icon: AlertOctagon,family: 'risk'     },
  Other:               { color: '#cbd5e1', icon: Sparkles,    family: 'new'      },
};

const familyBorder = {
  champion: 'border-amber-500',
  loyal: 'border-blue-500',
  risk: 'border-red-500',
  new: 'border-emerald-500',
} as const;

export default function SegmentationPage() {
  const language = useUiStore((s) => s.language);
  const [data, setData] = useState<RfmResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    analyticsApi
      .get('rfm') // → resolves to A02_rfm_scoring via backend mapping
      .then((res) => {
        const r = res.data?.result_json as RfmResult;
        setData(r);
        setError(null);
      })
      .catch((e) => {
        setError(e?.response?.data?.detail || t('seg_noData', language));
      })
      .finally(() => setLoading(false));
  }, []);

  // Scatter data: each top customer is a point colored by segment.
  const scatterBySegment = useMemo(() => {
    if (!data) return {} as Record<string, TopCustomer[]>;
    return data.top_customers.reduce<Record<string, TopCustomer[]>>((acc, c) => {
      acc[c.segment] ||= [];
      acc[c.segment].push(c);
      return acc;
    }, {});
  }, [data]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-gray-50 dark:bg-[#0f1115]">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-gray-50 dark:bg-[#0f1115]">
        <div className="max-w-md text-center">
          <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-300">{error || 'No data'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex min-w-0 bg-gray-50 dark:bg-[#0f1115] relative z-0 overflow-hidden animate-fade-in">
      <div className="flex-1 flex flex-col p-6 overflow-hidden">
        {/* Header */}
        <div className="mb-4">
          <h1 className="text-gray-900 dark:text-white text-3xl font-bold leading-tight mb-2">
            {t('seg_title', language)}
          </h1>
          <p className="text-slate-500 dark:text-[#9da6b9] text-sm">
            {tp('seg_subtitle', language, {
              n: data.summary.n_customers.toLocaleString(),
              date: data.summary.snapshot_date || '',
            })}
          </p>
        </div>

        {/* Top metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-white dark:bg-[#1a1d21] rounded-xl border border-gray-200 dark:border-[#282e39] p-4">
            <p className="text-xs uppercase tracking-wider text-slate-500">{t('seg_metrics_customers', language)}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              {data.summary.n_customers.toLocaleString()}
            </p>
          </div>
          <div className="bg-white dark:bg-[#1a1d21] rounded-xl border border-gray-200 dark:border-[#282e39] p-4">
            <p className="text-xs uppercase tracking-wider text-slate-500">{t('seg_metrics_revenue', language)}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              ${data.summary.total_revenue.toLocaleString()}
            </p>
          </div>
          <div className="bg-white dark:bg-[#1a1d21] rounded-xl border border-gray-200 dark:border-[#282e39] p-4">
            <p className="text-xs uppercase tracking-wider text-slate-500">{t('seg_metrics_avgRecency', language)}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              {data.summary.avg_recency.toFixed(0)}d
            </p>
          </div>
          <div className="bg-white dark:bg-[#1a1d21] rounded-xl border border-gray-200 dark:border-[#282e39] p-4">
            <p className="text-xs uppercase tracking-wider text-slate-500">{t('seg_metrics_avgMonetary', language)}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              ${data.summary.avg_monetary.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </p>
          </div>
        </div>

        {/* Scatter — real top customers, x=frequency, y=monetary, size=recency */}
        <div className="flex-1 min-h-[300px] bg-white dark:bg-[#1a1d21] rounded-xl border border-gray-200 dark:border-[#282e39] p-4">
          <h3 className="text-gray-900 dark:text-white font-bold mb-2">{t('seg_scatterTitle', language)}</h3>
          <ResponsiveContainer width="100%" height="92%">
            <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                type="number"
                dataKey="frequency"
                name="Frequency"
                tick={{ fontSize: 11 }}
                label={{ value: 'Orders (frequency)', position: 'bottom', offset: 0, fontSize: 12 }}
              />
              <YAxis
                type="number"
                dataKey="monetary"
                name="Monetary"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `$${Math.round(v / 1000)}k`}
                label={{ value: 'Total spend', angle: -90, position: 'insideLeft', fontSize: 12 }}
              />
              <ZAxis type="number" dataKey="recency_days" range={[60, 400]} name="Recency" />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                formatter={(v: any, n: any) => {
                  if (n === 'Monetary') return [`$${Number(v).toLocaleString()}`, n];
                  if (n === 'Recency') return [`${v} days`, 'Recency'];
                  return [v, n];
                }}
                contentStyle={{ borderRadius: 8 }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {Object.entries(scatterBySegment).map(([segment, points]) => {
                const style = SEGMENT_STYLES[segment] || SEGMENT_STYLES.Other;
                return (
                  <Scatter
                    key={segment}
                    name={`${segment} (${points.length})`}
                    data={points}
                    fill={style.color}
                    fillOpacity={0.75}
                  />
                );
              })}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Right sidebar — real segments */}
      <aside className="hidden xl:flex w-[360px] bg-white dark:bg-[#1a1d21] border-s border-gray-200 dark:border-[#282e39] flex-col shrink-0 z-10 shadow-2xl">
        <div className="p-6 border-b border-gray-200 dark:border-[#282e39]">
          <h2 className="text-gray-900 dark:text-white text-lg font-bold mb-1">{t('seg_sidebarTitle', language)}</h2>
          <p className="text-slate-500 dark:text-[#9da6b9] text-sm">
            {data.summary.n_customers.toLocaleString()} {t('seg_sidebarSubtitle', language)}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {data.segments.map((s) => {
            const style = SEGMENT_STYLES[s.segment] || SEGMENT_STYLES.Other;
            const Icon = style.icon;
            return (
              <div
                key={s.segment}
                className={`bg-gray-50 dark:bg-[#22262d] hover:bg-gray-100 dark:hover:bg-[#282e39] border-s-4 ${familyBorder[style.family]} rounded-xl p-4 shadow-sm transition-all cursor-pointer`}
              >
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-2">
                    <Icon className="w-5 h-5" style={{ color: style.color }} />
                    <h3 className="text-gray-900 dark:text-white font-semibold">{s.segment}</h3>
                  </div>
                  <span
                    className="text-xs px-2 py-1 rounded font-medium"
                    style={{ background: `${style.color}22`, color: style.color }}
                  >
                    {s.pct.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between items-end mb-2">
                  <span className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">
                    {s.count.toLocaleString()}
                  </span>
                  <span className="text-sm text-slate-500">customers</span>
                </div>
                <div className="space-y-1 mt-2">
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{t('seg_avgLtv', language)}</span>
                    <span className="text-gray-900 dark:text-white font-mono">
                      ${Math.round(s.avg_monetary).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{t('seg_revShare', language)}</span>
                    <span className="text-gray-900 dark:text-white font-mono">{s.rev_pct.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-[#111318] rounded-full h-1.5 overflow-hidden mt-1.5">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${Math.min(100, s.rev_pct)}%`, background: style.color }}
                    ></div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="p-6 pt-4 border-t border-gray-200 dark:border-[#282e39] bg-white dark:bg-[#1a1d21]">
          <button className="w-full bg-primary hover:bg-primary-hover text-white font-medium h-12 rounded-lg transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2 cursor-pointer">
            <Target className="w-5 h-5" />
            {t('seg_createCampaign', language)}
          </button>
        </div>
      </aside>
    </div>
  );
}
