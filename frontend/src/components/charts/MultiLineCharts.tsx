"use client";

/**
 * Multi-line time-series charts:
 *   A08 AOV Trends, A13 Growth Rates,
 *   A23 Product Life-Cycle Decay, C06 Customer Activity Timeline,
 *   P04 Product Sales Trend.
 */

import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid, AreaChart, Area, ReferenceLine } from "recharts";
import { InsightCard } from "./foundation/InsightCard";
import { InsightTooltip } from "./foundation/InsightTooltip";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";
import { fmtCompact, paletteColor, NoDataState, useChartTheme } from "./chartHelpers";
import { useAuthStore } from "@/stores/authStore";
import { useJobStore } from "@/stores/jobStore";
import { formatMoney } from "@/lib/format";

interface SeriesRow { period: string; [k: string]: any; }

function MultiLine({ rows, seriesKeys, yFormatter, currency, sourceCurrency }: {
  rows: SeriesRow[];
  seriesKeys: string[];
  /** Widened to match Recharts/InsightTooltip payload typing (`string | number`). */
  yFormatter?: (v: number | string) => string;
  currency?: string;
  sourceCurrency?: string;
}) {
  const theme = useChartTheme();
  if (rows.length === 0 || seriesKeys.length === 0) return <NoDataState />;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={theme.gridStroke} opacity={0.25} />
        <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} minTickGap={25} />
        <YAxis tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} tickFormatter={yFormatter || ((v) => fmtCompact(v))} />
        <Tooltip content={<InsightTooltip currency={currency} sourceCurrency={sourceCurrency} valueFormatter={yFormatter} />} />
        <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
        {seriesKeys.map((k, i) => (
          <Line key={k} type="monotone" dataKey={k} name={k} stroke={paletteColor(i)} strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} isAnimationActive={true} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ── A08 AOV Trends · Decision-Chart v1 ─────────────────────────────────
   Question: "Is each order getting bigger or smaller?"                  */
export function A08AOVTrendsChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const theme = useChartTheme();
  const user = useAuthStore((s) => s.user);
  const currency = user?.preferred_currency || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const headline = data?.headline ?? {};
  const question = data?.question || "Is each order getting bigger or smaller?";

  const monthly: any[] = data?.by_period?.monthly || data?.monthly || [];
  if (monthly.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A08"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="average order value"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState />
      </DecisionCardShell>
    );
  }

  const rows = monthly.map((m: any) => ({
    period: String(m.period || m.label || ""),
    aov: Number(m.aov ?? m.avg_order_value ?? 0),
  }));

  const summary = data?.summary || {};
  const currentAov = Number(summary.current_aov ?? summary.aov ?? rows[rows.length - 1]?.aov ?? 0);
  const yoyRef = rows.length >= 13 ? rows[rows.length - 13] : rows[0];
  const yoyPct = yoyRef && yoyRef.aov > 0 ? ((currentAov - yoyRef.aov) / yoyRef.aov) * 100 : 0;
  const orderFreq = Number(summary.order_frequency ?? summary.avg_orders_per_customer ?? 0);
  const target = Number(summary.target_aov ?? Math.round(currentAov * 1.05));

  const distRaw: any[] = data?.aov_distribution || data?.bucket_distribution || [];
  const distTotal = distRaw.reduce((s, b) => s + Number(b.count ?? b.pct ?? 0), 0);
  const dist = distRaw.map((b) => {
    const v = Number(b.count ?? 0);
    const pct = b.pct != null ? Number(b.pct) : distTotal > 0 ? (v / distTotal) * 100 : 0;
    return { label: String(b.bucket || b.label || ""), pct };
  });
  const maxBucket = dist.length ? dist.reduce((m, b) => (b.pct > m.pct ? b : m)) : null;

  const positive = yoyPct >= 0;

  return (
    <DecisionCardShell
      moduleKey="A08"
      question={question}
      period={headline.period || "Monthly trend"}
      headlineValue={formatMoney(Number(headline.value ?? currentAov), currency, { from: sourceCurrency })}
      headlineLabel={headline.label || "current AOV"}
      trendPct={headline.trend_pct ?? yoyPct}
      trendPeriod={headline.trend_pct != null ? "vs prior period" : "vs last year"}
      headlineKind={positive ? "positive" : "warning"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="grid grid-cols-3 gap-3 pb-3 mb-3 border-b border-gray-100 dark:border-white/5">
        <div className="rounded-lg bg-gray-50/50 dark:bg-white/[0.02] p-3 flex flex-col justify-center">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Current AOV</p>
          <p className="text-lg font-bold mt-1 text-primary">{formatMoney(currentAov, currency, { from: sourceCurrency })}</p>
        </div>
        <div className="rounded-lg bg-gray-50/50 dark:bg-white/[0.02] p-3 flex flex-col justify-center">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">YoY Growth</p>
          <div className="flex items-baseline gap-1.5 mt-1">
            <p className="text-lg font-bold dark:text-white">{positive ? "+" : ""}{yoyPct.toFixed(1)}%</p>
            <span className={`text-[11px] font-bold ${positive ? "text-emerald-500" : "text-amber-500"}`}>{positive ? "↑" : "↓"}</span>
          </div>
        </div>
        <div className="rounded-lg bg-gray-50/50 dark:bg-white/[0.02] p-3 flex flex-col justify-center">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Order Frequency</p>
          <p className="text-lg font-bold mt-1 dark:text-white">{orderFreq > 0 ? `${orderFreq.toFixed(1)}x` : "—"}</p>
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-4">
        <div className="flex-1 min-h-[220px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rows} margin={{ top: 6, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="a08-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={theme.primary} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={theme.primary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={theme.gridStroke} opacity={0.4} />
              <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} minTickGap={14} />
              <YAxis tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} tickFormatter={(v) => formatMoney(v, currency, { from: sourceCurrency, compact: true })} />
              <Tooltip content={<InsightTooltip currency={currency} sourceCurrency={sourceCurrency} />} />
              {target > 0 && <ReferenceLine y={target} stroke={theme.primary} strokeOpacity={0.5} strokeDasharray="6 4" />}
              <Area type="monotone" dataKey="aov" name="AOV" stroke={theme.primary} strokeWidth={3} fill="url(#a08-fill)" activeDot={{ r: 6, strokeWidth: 0, fill: theme.primary }} isAnimationActive={true} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <aside className="w-full lg:w-48 flex flex-col justify-end">
          <h4 className="text-xs font-semibold mb-3 text-slate-600 dark:text-slate-300">AOV Distribution</h4>
          {dist.length === 0 ? (
            <p className="text-xs text-slate-400">No distribution data.</p>
          ) : (
            <div className="flex flex-col gap-2.5">
              {dist.map((b) => {
                const isTop = maxBucket && b.label === maxBucket.label;
                return (
                  <div key={b.label} className="flex items-center gap-2 group">
                    <span className="w-12 text-right text-xs text-slate-500 font-medium truncate" title={b.label}>{b.label}</span>
                    <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-white/5 overflow-hidden">
                      <div className={`h-full rounded-full transition-all duration-500 ${isTop ? "bg-gradient-to-r from-primary/80 to-primary" : "bg-slate-300 dark:bg-slate-600 group-hover:bg-slate-400 dark:group-hover:bg-slate-500"}`} style={{ width: `${Math.max(2, b.pct)}%` }} />
                    </div>
                    <span className={`w-8 text-[11px] text-right ${isTop ? "text-primary font-bold" : "text-slate-400"}`}>{b.pct.toFixed(0)}%</span>
                  </div>
                );
              })}
            </div>
          )}
        </aside>
      </div>
    </DecisionCardShell>
  );
}

/* ── A13 Growth Rates · Decision-Chart v1 ───────────────────────────────
   Question: "Am I growing month-over-month and year-over-year?"        */
export function A13GrowthRatesChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const theme = useChartTheme();
  const headline = data?.headline ?? {};
  const question = data?.question || "Am I growing month-over-month and year-over-year?";

  const series: any[] = data?.monthly || data?.growth_rates || data?.series || [];
  if (series.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A13"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="growth rate"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState />
      </DecisionCardShell>
    );
  }

  const rows = series.map((m: any) => ({
    period: String(m.period || m.label || ""),
    revenue: Number(m.revenue_growth_pct ?? m.mom_pct ?? m.revenue_pct ?? 0),
    users:   Number(m.user_acquisition_pct ?? m.users_pct ?? m.new_customers_pct ?? 0),
    orders:  Number(m.order_velocity_pct ?? m.orders_pct ?? m.order_growth_pct ?? 0),
  }));

  const summary = data?.summary || {};
  const avgGrowth = Number(summary.avg_growth_pct ?? rows.reduce((s, r) => s + r.revenue, 0) / Math.max(1, rows.length));
  const peakRow = rows.reduce((best, r) => (r.revenue > best.revenue ? r : best), rows[0]);
  const lastRevPct = rows[rows.length - 1]?.revenue ?? 0;
  const momentum = lastRevPct >= 5 ? "Strong" : lastRevPct >= 0 ? "Steady" : "Soft";

  return (
    <DecisionCardShell
      moduleKey="A13"
      question={question}
      period={headline.period || "Monthly trend"}
      headlineValue={`${avgGrowth >= 0 ? "+" : ""}${avgGrowth.toFixed(1)}%`}
      headlineLabel={headline.label || "avg revenue growth"}
      trendPct={headline.trend_pct ?? lastRevPct}
      trendPeriod={headline.trend_pct != null ? "vs prior period" : "latest period"}
      headlineKind={avgGrowth >= 5 ? "positive" : avgGrowth >= 0 ? "neutral" : "warning"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex flex-wrap gap-4 mb-3">
        {[
          { name: "Revenue Growth (%)", color: theme.primary },
          { name: "User Acquisition (%)", color: "#8b5cf6" },
          { name: "Order Velocity (%)", color: "#10b981" },
        ].map((s) => (
          <span key={s.name} className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300 font-medium">
            <span className="w-2.5 h-2.5 rounded-full shadow-sm" style={{ backgroundColor: s.color }} />
            {s.name}
          </span>
        ))}
      </div>

      <div className="flex-1 min-h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid stroke={theme.gridStroke} strokeDasharray="3 3" vertical={false} opacity={0.4} />
            <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} minTickGap={14} />
            <YAxis tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v >= 0 ? "+" : ""}${v}%`} />
            <ReferenceLine y={0} stroke={theme.gridStroke} strokeWidth={1} />
            <Tooltip content={<InsightTooltip valueFormatter={(v) => `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(1)}%`} />} cursor={{ stroke: 'rgba(255,255,255,0.1)' }} />
            <Line type="monotone" name="Revenue" dataKey="revenue" stroke={theme.primary} strokeWidth={3} dot={false} activeDot={{ r: 5, strokeWidth: 0 }} />
            <Line type="monotone" name="Users" dataKey="users" stroke="#8b5cf6" strokeWidth={3} dot={false} activeDot={{ r: 5, strokeWidth: 0 }} />
            <Line type="monotone" name="Orders" dataKey="orders" stroke="#10b981" strokeWidth={3} strokeDasharray="5 5" dot={false} activeDot={{ r: 5, strokeWidth: 0 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-gray-100 dark:border-white/5">
        <div className="bg-gray-50/50 dark:bg-white/[0.02] rounded-lg p-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Avg Growth</p>
          <p className="text-lg font-bold mt-1 dark:text-white">{avgGrowth >= 0 ? "+" : ""}{avgGrowth.toFixed(1)}%</p>
        </div>
        <div className="bg-gray-50/50 dark:bg-white/[0.02] rounded-lg p-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Peak Growth</p>
          <div className="flex items-baseline gap-2 mt-1">
            <p className="text-lg font-bold text-primary">{peakRow.revenue >= 0 ? "+" : ""}{peakRow.revenue.toFixed(1)}%</p>
          </div>
        </div>
        <div className="bg-gray-50/50 dark:bg-white/[0.02] rounded-lg p-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Momentum</p>
          <div className="flex items-baseline gap-2 mt-1">
            <p className="text-lg font-bold dark:text-white">{momentum}</p>
          </div>
        </div>
      </div>
    </DecisionCardShell>
  );
}

/* ── A23 Product Life-Cycle ──────────────────────────────────────────────── */
const STAGE_COLORS: Record<string, string> = {
  growing: "#10b981", growth: "#10b981",
  introduction: "#0ea5e9", introducing: "#0ea5e9",
  mature: "#137fec", maturity: "#137fec",
  declining: "#f43f5e", decline: "#f43f5e",
  decay: "#f97316",
};

/* ── A23 Product Life-Cycle · Decision-Chart v1 ─────────────────────────
   Question: "Which products are growing, maturing, or dying?"          */
export function A23LifecycleChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const byStage: Array<{ stage: string; count: number }> = data?.by_stage || [];
  const topRev: Array<{ name?: string; product_id: string; stage?: string; revenue: number }> = data?.top_by_revenue || [];
  const headline = data?.headline ?? {};
  const question = data?.question || "Which products are growing, maturing, or dying?";

  if (byStage.length === 0 && topRev.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A23"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="products tracked"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState />
      </DecisionCardShell>
    );
  }

  const maxCount = Math.max(...byStage.map((s) => s.count), 1);
  const maxRev = Math.max(...topRev.map((p) => Number(p.revenue) || 0), 1);
  const growingCount = byStage.find((s) => /grow/.test(s.stage.toLowerCase()))?.count ?? 0;
  const decliningCount = byStage.find((s) => /declin|decay/.test(s.stage.toLowerCase()))?.count ?? 0;

  return (
    <DecisionCardShell
      moduleKey="A23"
      question={question}
      period={headline.period || "Lifecycle snapshot"}
      headlineValue={String(headline.value ?? growingCount)}
      headlineLabel={headline.label || `products in growth · ${decliningCount} declining`}
      headlineKind={growingCount >= decliningCount ? "positive" : "warning"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="w-full flex-1 flex flex-col gap-4 overflow-auto custom-scrollbar">
        {byStage.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-3">Portfolio Distribution</p>
            <div className="space-y-3">
              {byStage.map((s) => {
                const colour = STAGE_COLORS[s.stage.toLowerCase()] || "#94a3b8";
                return (
                  <div key={s.stage} className="flex items-center gap-3">
                    <span className="w-20 capitalize text-sm font-medium text-slate-600 dark:text-slate-400">{s.stage}</span>
                    <div className="flex-1 h-2 rounded-full overflow-hidden bg-slate-100 dark:bg-white/5">
                      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${(s.count / maxCount) * 100}%`, backgroundColor: colour }} />
                    </div>
                    <span className="w-8 text-right font-bold text-xs text-slate-700 dark:text-slate-300">{s.count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {topRev.length > 0 && (
          <div className="flex-1 min-h-0">
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-3">Top Movers</p>
            <div className="space-y-3">
              {topRev.slice(0, 5).map((p) => {
                const colour = STAGE_COLORS[(p.stage || "").toLowerCase()] || "#94a3b8";
                const safeRev = Number(p.revenue ?? 0);
                const widthPct = maxRev > 0 ? (safeRev / maxRev) * 100 : 0;
                return (
                  <div key={p.product_id} className="flex items-center gap-3 group">
                    <span className="w-2 h-2 rounded-full shrink-0 shadow-sm" style={{ backgroundColor: colour }} title={p.stage} />
                    <span className="flex-1 truncate text-sm font-medium text-slate-700 dark:text-slate-200" title={p.name || p.product_id}>{p.name || p.product_id}</span>
                    <div className="w-24 h-2 rounded-full overflow-hidden bg-slate-100 dark:bg-white/5">
                      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.max(2, widthPct)}%`, backgroundColor: colour, opacity: 0.8 }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </DecisionCardShell>
  );
}

/* ── P04 Product Sales Trend · Decision-Chart v1 ────────────────────────
   Question: "Is each product's sales trending up or down?"             */
export function P04ProductSalesTrendChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const theme = useChartTheme();
  const user = useAuthStore((s) => s.user);
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const currency = user?.preferred_currency || 'USD';
  const headline = data?.headline ?? {};
  const question = data?.question || "Is each product's sales trending up or down?";

  const series = data?.by_product_trend || data?.series || data?.lifecycle_curves || [];
  if (series.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="P04"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="top product trend"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState />
      </DecisionCardShell>
    );
  }
  
  const top5 = series.slice(0, 5);

  // Build one row per product with: name, sparkline points, trend %.
  // Trend = ((last - first) / first) * 100. The arrow + colour is the
  // one-glance answer; the sparkline shows the path.
  const rows: Array<{ name: string; pts: number[]; last: number; trendPct: number }> = top5.map((s: any, i: number) => {
    const pts: number[] = (s.points || []).map((p: any) => Number(p.revenue ?? p.quantity ?? 0));
    const first = pts[0] ?? 0;
    const last = pts[pts.length - 1] ?? 0;
    const trendPct = first > 0 ? ((last - first) / first) * 100 : 0;
    return {
      name: s.product_name || s.name || s.product_id || `Product ${i + 1}`,
      pts,
      last,
      trendPct,
    };
  });
  const maxPt = Math.max(
    ...rows.flatMap((r) => r.pts),
    1,
  );

  const topProduct = top5[0];
  const topName = topProduct?.product_name || topProduct?.name || topProduct?.product_id;

  return (
    <DecisionCardShell
      moduleKey="P04"
      question={question}
      period={headline.period || "All time"}
      headlineValue={topName ? String(topName).slice(0, 24) : "—"}
      headlineLabel={headline.label || "top product trend"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      {/* ── Per-product sparkline + trend list · the direct visual answer ──
          Each row literally shows "is this product up or down?" via an
          arrow and a sparkline. Reading the list top-to-bottom answers
          the question for ALL top-5 products in one glance. */}
      <ul className="space-y-1.5 flex-1 min-h-0 overflow-auto custom-scrollbar pr-0.5">
        {rows.map((r, idx) => {
          const up = r.trendPct >= 1;
          const down = r.trendPct <= -1;
          const flat = !up && !down;
          const color = up ? theme.semantic.positive : down ? theme.semantic.danger : theme.text.muted;
          const bg = idx === 0 ? theme.semanticSoft.brand : theme.surfaceMuted;
          // Build sparkline path
          const sparkPath = (() => {
            if (r.pts.length < 2) return "";
            const w = 100, h = 30;
            return r.pts.map((v, i) => {
              const x = (i / (r.pts.length - 1)) * w;
              const y = h - (v / maxPt) * (h - 4) - 2;
              return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
            }).join(" ");
          })();
          return (
            <li
              key={`${r.name}-${idx}`}
              className="rounded-md px-2.5 py-1.5 flex items-center gap-2.5"
              style={{
                background: bg,
                border: `1px solid ${idx === 0 ? theme.semantic.brand + "44" : theme.border}`,
              }}
            >
              <span
                className="text-[10px] font-extrabold w-4 text-center tabular-nums"
                style={{ color: idx === 0 ? theme.semantic.brand : theme.text.faint }}
              >
                {idx + 1}
              </span>
              <span
                className="text-[11.5px] font-semibold flex-1 truncate"
                style={{ color: theme.text.headline }}
                title={r.name}
              >
                {r.name}
              </span>
              {/* Mini sparkline */}
              <svg
                viewBox="0 0 100 30"
                preserveAspectRatio="none"
                className="w-20 h-7 shrink-0"
              >
                <path
                  d={sparkPath}
                  fill="none"
                  stroke={color}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              {/* Trend arrow + % */}
              <span
                className="text-[11px] font-extrabold tabular-nums w-16 text-right shrink-0 inline-flex items-center justify-end gap-0.5"
                style={{ color }}
              >
                {up && "↑"}
                {down && "↓"}
                {flat && "→"}
                {r.trendPct >= 0 ? "+" : ""}{r.trendPct.toFixed(1)}%
              </span>
              {/* Last value */}
              <span
                className="text-[10px] tabular-nums w-16 text-right shrink-0"
                style={{ color: theme.text.muted }}
              >
                {formatMoney(r.last, currency, { from: sourceCurrency, compact: true })}
              </span>
            </li>
          );
        })}
      </ul>
    </DecisionCardShell>
  );
}
