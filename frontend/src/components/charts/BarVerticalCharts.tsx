"use client";

/**
 * Vertical bar charts for categorical comparisons:
 *   A21 Return Rate, A25 Stockout Risk, P03 Brand Performance.
 */

import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, CartesianGrid } from "recharts";
import { InsightCard } from "./foundation/InsightCard";
import { InsightTooltip } from "./foundation/InsightTooltip";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";
import { fmtCompact, fmtPct, truncate, paletteColor, NoDataState, useChartTheme } from "./chartHelpers";
import { useAuthStore } from "@/stores/authStore";
import { useJobStore } from "@/stores/jobStore";
import { formatMoney } from "@/lib/format";

interface CatRow { label: string; value: number; }
interface VerticalBarProps {
  rows: CatRow[];
  /** Widened to match InsightTooltip's signature — Recharts payload values
   *  can be string or number. Inside chart callsites we coerce with Number(). */
  valueFormatter?: (v: number | string) => string;
  yLabel?: string;
}

function VerticalBar({ rows, valueFormatter = (v) => fmtCompact(Number(v)) }: VerticalBarProps) {
  const theme = useChartTheme();
  if (rows.length === 0) return <NoDataState />;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows.slice(0, 15)} margin={{ top: 10, right: 0, left: -20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={theme.gridStroke} opacity={0.4} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: '#888' }}
          tickLine={false}
          axisLine={false}
          interval={0}
          angle={-35}
          textAnchor="end"
          height={60}
          tickFormatter={(v: string) => truncate(v, 14)}
        />
        <YAxis tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} tickFormatter={(v) => fmtCompact(v, 0)} width={60} />
        <Tooltip content={<InsightTooltip valueFormatter={valueFormatter} />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {rows.slice(0, 15).map((_, i) => (
            <Cell key={i} fill={i === 0 ? "var(--primary)" : i === 1 ? "#8b5cf6" : i === 2 ? "#38bdf8" : "#94a3b8"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── A21 Return Rate · Decision-Chart v1 ────────────────────────────────
   Question: "Which products are getting returned the most?"             */
export function A21ReturnRateChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const list = data?.highest_return_products || data?.by_product || data?.top_returns || [];
  const rows = list.map((p: any) => ({
    label: p.name || p.product_name || p.product_id,
    value: Number(p.return_rate_pct ?? p.return_rate ?? p.rate ?? 0),
  }));
  const summary = data?.summary || {};
  const headline = data?.headline ?? {};
  const question = data?.question || "Which products are getting returned the most?";
  const overallRate = Number(headline.value ?? summary.overall_return_rate_pct ?? summary.return_rate_pct ?? 0);

  return (
    <DecisionCardShell
      moduleKey="A21"
      question={question}
      period={headline.period || "All time"}
      headlineValue={`${overallRate.toFixed(1)}%`}
      headlineLabel={headline.label || "overall return rate"}
      headlineKind={overallRate >= 10 ? "danger" : overallRate >= 5 ? "warning" : "positive"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[180px]">
        <VerticalBar rows={rows} valueFormatter={(v) => fmtPct(Number(v), 1)} />
      </div>
    </DecisionCardShell>
  );
}

/* ── A25 Stockout Risk · Decision-Chart v1 ──────────────────────────────
   Question: "Which products am I about to run out of?"                  */
export function A25StockoutChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const theme = useChartTheme();
  const list = data?.critical_products || data?.all_products || [];
  const rows = list.slice(0, 15).map((p: any) => ({
    label: p.name || p.product_name || p.product_id,
    value: Math.max(0, Number(p.days_to_stockout ?? p.days_until_stockout ?? p.days_left ?? p.risk_score ?? 0)),
  }));
  const summary = data?.summary || {};
  const headline = data?.headline ?? {};
  const question = data?.question || "Which products am I about to run out of?";

  const nCritical = Number(summary.critical_count ?? 0);
  const nWarning = Number(summary.warning_count ?? 0);
  const nOut = Number(summary.out_of_stock_count ?? 0);
  const needsAttention = Number(headline.value ?? (nCritical + nWarning + nOut));

  // Small pill cluster — slot into headerRight so the user sees the breakdown
  const headerRight = (
    <div className="flex gap-1.5">
      <div
        className="rounded-md px-2 py-1 text-center"
        style={{
          background: theme.semanticSoft.danger,
          border: `1px solid ${theme.semantic.danger}40`,
        }}
      >
        <p
          className="text-[8px] uppercase tracking-wider font-bold"
          style={{ color: theme.semantic.danger }}
        >Out</p>
        <p className="text-xs font-bold" style={{ color: theme.semantic.danger }}>{nOut}</p>
      </div>
      <div
        className="rounded-md px-2 py-1 text-center"
        style={{
          background: theme.semanticSoft.warning,
          border: `1px solid ${theme.semantic.warning}40`,
        }}
      >
        <p
          className="text-[8px] uppercase tracking-wider font-bold"
          style={{ color: theme.semantic.warning }}
        >Risk</p>
        <p className="text-xs font-bold" style={{ color: theme.semantic.warning }}>{nCritical + nWarning}</p>
      </div>
    </div>
  );

  return (
    <DecisionCardShell
      moduleKey="A25"
      question={question}
      period={headline.period || "30-day velocity window"}
      headlineValue={needsAttention.toLocaleString()}
      headlineLabel={headline.label || "SKUs need restock attention"}
      trendPct={null}
      headlineKind={
        nOut + nCritical >= 1 ? "danger" :
        nWarning >= 1 ? "warning" : "positive"
      }
      headerRight={headerRight}
      aiInsight={
        <AIInsightPanel moduleKey={moduleKey} question={question} data={data} />
      }
      actions={
        <ActionChipRow
          actions={(data?.suggested_actions as SuggestedAction[]) || []}
          onAction={(a) => { void a; }}
        />
      }
    >
      <div className="flex-1 min-h-[180px]">
        <VerticalBar rows={rows} valueFormatter={(v) => `${Number(v).toFixed(0)}d`} />
      </div>
    </DecisionCardShell>
  );
}

/* ── P03 Brand Performance · Decision-Chart v1 ──────────────────────────
   Question: "Which of my suppliers / brands is performing best?"        */
export function P03BrandPerformanceChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const user = useAuthStore((s) => s.user);
  const currency = user?.preferred_currency || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);

  const list = data?.by_brand || data?.brands || [];
  const rows = list.map((b: any) => ({
    label: b.brand || b.name || "",
    value: Number(b.revenue ?? b.total ?? 0),
  }));
  const headline = data?.headline ?? {};
  const summary = data?.summary || {};
  const question = data?.question || "Which of my suppliers / brands is performing best?";
  const topBrand = summary.top_brand || list[0];

  return (
    <DecisionCardShell
      moduleKey="P03"
      question={question}
      period={headline.period || "All time"}
      headlineValue={topBrand ? truncate(String(topBrand.brand || topBrand.name || "—"), 22) : "—"}
      headlineLabel={
        topBrand
          ? `top brand · ${formatMoney(Number(topBrand.revenue || 0), currency, { from: sourceCurrency })}`
          : "no brand data"
      }
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[180px]">
        <VerticalBar rows={rows} valueFormatter={(v) => formatMoney(Number(v), currency, { from: sourceCurrency, compact: true })} />
      </div>
    </DecisionCardShell>
  );
}

/* ── A26 Sentiment vs LTV · Decision-Chart v1 ───────────────────────────
   Question: "Do happier customers spend more with me?"                 */
export function A26SentimentLTVChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const user = useAuthStore((s) => s.user);
  const currency = user?.preferred_currency || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);

  const list = data?.by_sentiment || [];
  const rows = list.map((b: any) => ({
    label: String(b.bucket || b.sentiment || ""),
    value: Number(b.avg_ltv ?? b.avg_lifetime_value ?? 0),
  }));
  const summary = data?.summary || {};
  const corr = Number(summary.pearson_correlation ?? 0);
  const headline = data?.headline ?? {};
  const question = data?.question || "Do happier customers spend more with me?";

  return (
    <DecisionCardShell
      moduleKey="A26"
      question={question}
      period={headline.period || "All time"}
      headlineValue={`${corr > 0 ? "+" : ""}${corr.toFixed(2)}`}
      headlineLabel={headline.label || "sentiment ↔ LTV correlation"}
      headlineKind={corr >= 0.3 ? "positive" : corr <= -0.3 ? "danger" : "neutral"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[180px]">
        <VerticalBar rows={rows} valueFormatter={(v) => formatMoney(Number(v), currency, { from: sourceCurrency, compact: true })} />
      </div>
    </DecisionCardShell>
  );
}

/* ── C06 Activity Timeline ───────────────────────────────────────────────── */
/* ── C06 Activity Timeline · Decision-Chart v1 ──────────────────────────
   Question: "How often do my customers come back to buy again?"        */
export function C06ActivityTimelineChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const dist = data?.orders_per_customer_distribution || [];
  const rows = dist.map((b: any) => ({
    label: String(b.bucket || ""),
    value: Number(b.count || 0),
  }));
  const summary = data?.summary || {};
  const headline = data?.headline ?? {};
  const question = data?.question || "How often do my customers come back to buy again?";
  const repeatPct = Number(headline.value ?? summary.repeat_customer_pct ?? 0);

  return (
    <DecisionCardShell
      moduleKey="C06"
      question={question}
      period={headline.period || "All time"}
      headlineValue={`${repeatPct.toFixed(1)}%`}
      headlineLabel={headline.label || "customers who bought more than once"}
      headlineKind={repeatPct >= 40 ? "positive" : repeatPct >= 20 ? "neutral" : "warning"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[180px]">
        <VerticalBar rows={rows} valueFormatter={(v) => fmtCompact(Number(v))} />
      </div>
    </DecisionCardShell>
  );
}
