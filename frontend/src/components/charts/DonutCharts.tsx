"use client";

/**
 * Donut/pie charts for distribution-share modules:
 *   C01 Demographics, C05 Customer Segment Breakdown.
 *
 * A11 Order Status has its own donut (it embeds the success rate as a
 * centred badge — that's its specific value-add).
 */

import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from "recharts";
import { InsightCard } from "./foundation/InsightCard";
import { InsightTooltip } from "./foundation/InsightTooltip";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";
import { NoDataState, useChartTheme } from "./chartHelpers";

interface SliceRow { name: string; value: number; }

function Donut({ rows, centerLabel, centerSub }: { rows: SliceRow[]; centerLabel?: string; centerSub?: string }) {
  const theme = useChartTheme();
  if (rows.length === 0) return <NoDataState />;
  
  const total = rows.reduce((s, r) => s + r.value, 0) || 1;
  const colors = ["var(--primary)", "#8b5cf6", "#38bdf8", "#f43f5e", "#f59e0b", "#94a3b8"];

  return (
    <div className="relative w-full h-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart margin={{ top: 0, right: 0, left: 0, bottom: 20 }}>
          <Pie
            data={rows}
            dataKey="value"
            cx="50%"
            cy="50%"
            innerRadius="65%"
            outerRadius="85%"
            paddingAngle={3}
            isAnimationActive={true}
            stroke="var(--surface-card, #ffffff)"
            strokeWidth={2}
          >
            {rows.map((_, i) => (
              <Cell key={i} fill={colors[i % colors.length]} />
            ))}
          </Pie>
          <Tooltip content={<InsightTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
          <Legend wrapperStyle={{ fontSize: 11, fontWeight: 500 }} iconType="circle" />
        </PieChart>
      </ResponsiveContainer>
      {centerLabel && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none mb-5">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">{centerSub || "Total"}</p>
          <p className="text-2xl font-bold text-slate-800 dark:text-white mt-0.5">{centerLabel}</p>
        </div>
      )}
    </div>
  );
}

/* ── C01 Customer Demographics · Decision-Chart v1 ──────────────────────
   Question: "Who are my customers — what's their age/gender mix?"      */
export function C01DemographicsChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  let rows: SliceRow[] = [];
  let type = "Demographics";

  if (Array.isArray(data?.gender_distribution) && data.gender_distribution.length > 0) {
    rows = data.gender_distribution.map((r: any) => ({
      name: String(r.gender || r.label || r.name || "?"),
      value: Number(r.count || r.customers || r.value || 0),
    }));
    type = "Gender";
  } else if (Array.isArray(data?.age_distribution) && data.age_distribution.length > 0) {
    rows = data.age_distribution.map((r: any) => ({
      name: String(r.bucket || r.age_band || r.label || "?"),
      value: Number(r.count || r.customers || r.value || 0),
    }));
    type = "Age Group";
  }

  const total = rows.reduce((s, r) => s + r.value, 0);
  const headline = data?.headline ?? {};
  const question = data?.question || "Who are my customers — what's their age/gender mix?";
  const topSlice = rows.length ? rows.reduce((a, b) => (a.value > b.value ? a : b)) : null;
  const topPct = topSlice && total ? (topSlice.value / total) * 100 : 0;

  return (
    <DecisionCardShell
      moduleKey="C01"
      question={question}
      period={headline.period || "Customer snapshot"}
      headlineValue={topSlice ? `${topPct.toFixed(0)}%` : "—"}
      headlineLabel={
        topSlice
          ? `${topSlice.name} (largest ${type.toLowerCase()})`
          : `customers profiled by ${type.toLowerCase()}`
      }
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[200px]">
        <Donut rows={rows} centerLabel={total ? total.toLocaleString() : undefined} centerSub="Customers" />
      </div>
    </DecisionCardShell>
  );
}

/* ── C05 Customer Segment Breakdown · Decision-Chart v1 ─────────────────
   Question: "What's the mix of my customer segments?"                  */
export function C05SegmentBreakdownChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const segs = data?.segments || data?.by_segment || [];
  const rows: SliceRow[] = segs.map((s: any) => ({
    name: String(s.segment || s.name || ""),
    value: Number(s.count || s.customers || s.n_customers || 0),
  }));
  const total = rows.reduce((s, r) => s + r.value, 0);
  const headline = data?.headline ?? {};
  const question = data?.question || "What's the mix of my customer segments?";
  const top = rows.length ? rows.reduce((a, b) => (a.value > b.value ? a : b)) : null;

  return (
    <DecisionCardShell
      moduleKey="C05"
      question={question}
      period={headline.period || `${total.toLocaleString()} customers`}
      headlineValue={top ? top.name : "—"}
      headlineLabel={
        top
          ? `largest segment · ${(top.value / total * 100).toFixed(0)}%`
          : "no segments yet"
      }
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[200px]">
        <Donut rows={rows} centerLabel={total ? total.toLocaleString() : undefined} centerSub="Total" />
      </div>
    </DecisionCardShell>
  );
}
