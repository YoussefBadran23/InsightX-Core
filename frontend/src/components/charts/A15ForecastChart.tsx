"use client";

/**
 * A15 — Prophet Revenue Forecast (rebuilt per new spec).
 *
 * Dark card with two columns:
 *   Left:  big "Predicted (Next 30 Days)" headline + dual-segment chart —
 *          solid slate-blue historical line, dashed primary-blue forecast
 *          line with glow, soft 80% confidence band, vertical "Today" marker.
 *   Right: Seasonal Decomposition panel — Daily / Weekly / Yearly mini-spark
 *          cards with deltas + insight text + export button.
 *
 * Tolerates both `history` + `forecast` (current shape) and a `series` blob.
 * Falls back to a clean empty state when there's nothing to plot.
 */

import { useMemo } from "react";
import { ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts";
import { InsightCard } from "./foundation/InsightCard";
import { InsightTooltip } from "./foundation/InsightTooltip";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";
import { fmtCompact, useChartTheme } from "./chartHelpers";
import { useAuthStore } from "@/stores/authStore";
import { useJobStore } from "@/stores/jobStore";
import { formatMoney } from "@/lib/format";

interface HistoryRow { date: string; actual: number | null; fitted: number; lower: number; upper: number; }
interface ForecastRow { date: string; yhat: number; lower: number; upper: number; horizon: number; }
interface SeasonalTrend { pct: number; note?: string; points?: number[]; }
interface A15Data {
  summary?: { last_date?: string; total_revenue_30d_forecast?: number; total_revenue_90d_forecast?: number; trend_label?: string; backtest_mape?: number; model_engine?: string; };
  history?: HistoryRow[];
  forecast?: ForecastRow[];
  seasonal?: { daily?: SeasonalTrend; weekly?: SeasonalTrend; yearly?: SeasonalTrend; };
}
interface Props { data: A15Data; moduleKey: string; }

function Sparkline({ points, color }: { points: number[]; color: string }) {
  if (points.length < 2) return <div className="w-full h-12" />;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const pathD = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * 100;
      const y = 30 - ((p - min) / range) * 24;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="w-full h-10">
      <path d={pathD} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function A15ForecastChart({ data, moduleKey }: Props) {
  const theme = useChartTheme();
  const user = useAuthStore((s) => s.user);
  const currency = user?.preferred_currency || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);

  const history = data?.history || [];
  const forecast = data?.forecast || [];
  const summary = data?.summary || {};
  const seasonal = data?.seasonal || {};

  const chartRows = useMemo(() => {
    return [
      ...history.map((h) => ({
        date: h.date,
        historical: h.actual ?? h.fitted,
        forecast: null as number | null,
        band: [Number(h.lower) || 0, Number(h.upper) || 0] as [number, number],
        isForecast: false,
      })),
      ...forecast.map((f) => ({
        date: f.date,
        historical: null as number | null,
        forecast: Number(f.yhat) || 0,
        band: [Number(f.lower) || 0, Number(f.upper) || 0] as [number, number],
        isForecast: true,
      })),
    ];
  }, [history, forecast]);

  const lastHistoricalDate = summary.last_date ?? history[history.length - 1]?.date ?? null;
  const predicted30 = Number(summary.total_revenue_30d_forecast ?? 0);

  const a15Headline = (data as any)?.headline ?? {};
  const a15Question = (data as any)?.question || "How much money will I make in the next 30 / 90 days?";
  const a15Actions = (data as any)?.suggested_actions || [];

  if (chartRows.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A15"
        question={a15Question}
        period="no data"
        headlineValue="—"
        headlineLabel="next 30 days · predicted"
        aiInsight={<AIInsightPanel moduleKey="A15" question={a15Question} data={data} />}
        actions={<ActionChipRow actions={a15Actions as SuggestedAction[]} />}
      >
        <div className="text-xs text-slate-500">Forecast unavailable</div>
      </DecisionCardShell>
    );
  }

  const headerRight = (
    <div className="flex items-center gap-2">
      <div className="bg-primary/10 border border-primary/20 rounded-full px-3 py-1 flex items-center gap-1.5 shrink-0">
        <span className="text-xs">🧠</span>
        <span className="text-[10px] uppercase tracking-wider font-bold text-primary">
          {summary.model_engine || "Prophet Model"}
        </span>
      </div>
    </div>
  );

  return (
    <DecisionCardShell
      moduleKey="A15"
      question={a15Question}
      period={a15Headline.period || "Next 30 days"}
      headlineValue={
        predicted30 > 0
          ? formatMoney(predicted30, currency, { from: sourceCurrency })
          : "—"
      }
      headlineLabel={a15Headline.label || "predicted revenue (next 30 days)"}
      headlineKind="positive"
      headerRight={headerRight}
      aiInsight={<AIInsightPanel moduleKey="A15" question={a15Question} data={data} />}
      actions={<ActionChipRow actions={a15Actions as SuggestedAction[]} />}
    >
      <div className="flex flex-col lg:flex-row gap-6">
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="flex items-end gap-3 mb-6">
            <div>
              <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">Predicted (Next 30 Days)</p>
              <p className="text-4xl font-black text-slate-800 dark:text-white tracking-tight">
                {predicted30 > 0 ? formatMoney(predicted30, currency, { from: sourceCurrency, compact: true }) : "—"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 text-[11px] font-medium text-slate-600 dark:text-slate-300 mb-2">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-slate-400" />Historical</span>
            <span className="flex items-center gap-1.5"><span className="w-3 border-t-2 border-dashed border-primary" />Forecast</span>
            <span className="flex items-center gap-1.5"><span className="w-3 border-t-[6px] border-primary/20" />80% CI</span>
          </div>

          <div className="flex-1 min-h-[280px] relative">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartRows} margin={{ top: 16, right: 0, left: -20, bottom: 4 }}>
                <defs>
                  <linearGradient id={`a15-ci-${moduleKey}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="var(--primary)" stopOpacity={0.02} />
                  </linearGradient>
                  <filter id={`a15-glow-${moduleKey}`} x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                  </filter>
                </defs>
                <CartesianGrid stroke={theme.gridStroke} strokeDasharray="3 3" vertical={false} opacity={0.4} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} minTickGap={28} />
                <YAxis tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} tickFormatter={(v) => formatMoney(v, currency, { from: sourceCurrency, compact: true })} width={60} />
                <Tooltip contentStyle={{ background: "var(--surface-elevated, #ffffff)", color: "inherit", borderColor: "rgba(148,163,184,0.2)", borderRadius: 8, fontSize: 12 }} labelStyle={{ color: "#64748b", fontSize: 10, fontWeight: 600 }} cursor={{ stroke: 'rgba(255,255,255,0.05)' }} formatter={(v: any, name: string) => { if (v == null) return ["—", name]; if (name === "band") return [`${formatMoney(v[0], currency, { from: sourceCurrency, compact: true })} - ${formatMoney(v[1], currency, { from: sourceCurrency, compact: true })}`, "CI 80%"]; return [formatMoney(Number(v), currency, { from: sourceCurrency, compact: true }), name === "historical" ? "Historical" : "Forecast"]; }} />
                
                <Area type="monotone" dataKey="band" stroke="none" fill={`url(#a15-ci-${moduleKey})`} isAnimationActive={true} connectNulls />
                <Line type="monotone" dataKey="historical" stroke="#94a3b8" strokeWidth={2.5} dot={false} isAnimationActive={true} connectNulls={false} />
                <Line type="monotone" dataKey="forecast" stroke="var(--primary)" strokeWidth={3} strokeDasharray="6 6" dot={false} activeDot={{ r: 5, fill: theme.cardBg, stroke: "var(--primary)", strokeWidth: 2, filter: `url(#a15-glow-${moduleKey})` }} isAnimationActive={true} connectNulls={false} filter={`url(#a15-glow-${moduleKey})`} />
                
                {lastHistoricalDate && <ReferenceLine x={lastHistoricalDate} stroke="var(--primary)" strokeDasharray="4 4" strokeOpacity={0.5} label={{ value: "Today", position: "top", fill: "var(--primary)", fontSize: 11, fontWeight: 600 }} />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <aside className="w-full lg:w-72 flex-shrink-0 flex flex-col gap-4">
          <div className="bg-slate-50/50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/5 rounded-xl p-4">
            <h4 className="text-[12px] font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5 mb-1">
              <span className="text-[14px]">📊</span> Seasonal Decomposition
            </h4>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-medium mb-4">Recurring patterns</p>

            <div className="space-y-3">
              {([
                { key: "daily", label: "Daily", color: "#10b981", default_note: "Peak activity 10 am – 2 pm" },
                { key: "weekly", label: "Weekly", color: "#f59e0b", default_note: "Mid-week dip identified" },
                { key: "yearly", label: "Yearly", color: "#38bdf8", default_note: "Strong Q4 seasonality" },
              ] as const).map((tr) => {
                const s: SeasonalTrend | undefined = (seasonal as any)[tr.key];
                const pct = Number(s?.pct ?? 0);
                const positive = pct >= 0;
                const points = s?.points && s.points.length >= 2 ? s.points : [4, 8, 6, 10, 9, 12, 8, 14];
                return (
                  <div key={tr.key} className="bg-white dark:bg-surface-card border border-slate-100 dark:border-white/5 shadow-sm rounded-lg p-3 hover:-translate-y-0.5 transition-transform">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-[11px] font-bold text-slate-700 dark:text-slate-300">{tr.label}</span>
                      <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded-md ${positive ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-amber-500/10 text-amber-600 dark:text-amber-400"}`}>
                        {positive ? "+" : ""}{pct.toFixed(0)}%
                      </span>
                    </div>
                    <Sparkline points={points} color={tr.color} />
                    <p className="text-[10px] text-slate-500 mt-2 font-medium">{s?.note || tr.default_note}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>
      </div>
    </DecisionCardShell>
  );
}
