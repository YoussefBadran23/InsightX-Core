import { useMemo } from "react";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

import { useAuthStore } from "@/stores/authStore";
import { useJobStore } from "@/stores/jobStore";
import { formatMoney } from "@/lib/format";
import { useChartTheme } from "./chartHelpers";
import { InsightCard } from "./foundation/InsightCard";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";

interface Customer {
  customer_id: string;
  R: number;
  F: number;
  M: number;
  segment: string;
  recency_days?: number;
  frequency?: number;
  monetary?: number;
  RFM_score?: string;
}

interface A02Data {
  summary?: { n_customers?: number };
  segments?: Array<{ segment: string; count: number; pct: number; revenue: number }>;
  top_customers?: Customer[];
}

interface Props {
  data: A02Data;
  moduleKey: string;
}

const SEGMENT_FAMILY: Record<string, { color: string; label: string; blurb: string }> = {
  Champions:             { color: "#10b981", label: "Champions",        blurb: "Bought recently, buy often, spend the most." },
  "Loyal Customers":     { color: "#0053cd", label: "Loyal Customers",  blurb: "Spend good money and respond to promotions." },
  "Potential Loyalists": { color: "#a855f7", label: "Potential Loyalists", blurb: "Recent customers with average frequency." },
  "Need Attention":      { color: "#a855f7", label: "Need Attention",   blurb: "Middling on every dimension — winnable." },
  "New Customers":       { color: "#10b981", label: "New Customers",    blurb: "Just made their first purchase." },
  Promising:             { color: "#10b981", label: "Promising",        blurb: "Recent but low-value first orders." },
  "About to Sleep":      { color: "#f59e0b", label: "About to Sleep",   blurb: "Recency slipping, low frequency." },
  "At Risk":             { color: "#f59e0b", label: "At Risk",          blurb: "Spent big and often, but long ago." },
  "Cannot Lose Them":    { color: "#f59e0b", label: "Cannot Lose Them", blurb: "High-value loyal customers going quiet." },
  Hibernating:           { color: "#e11d48", label: "Hibernating",      blurb: "Long-dormant, low spenders." },
  Lost:                  { color: "#e11d48", label: "Lost",             blurb: "Long since gone, low engagement." },
  Other:                 { color: "#94a3b8", label: "Other",            blurb: "Doesn't fit a canonical bucket." },
};

const DEFAULT_VIZ = { color: "#94a3b8", label: "Unknown", blurb: "" };

export function A02RFM3DChart({ data, moduleKey }: Props & { moduleKey?: string }) {
  const theme = useChartTheme();
  const currency = useAuthStore((s) => s.user?.preferred_currency) || "USD";
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const headline = (data as any)?.headline ?? {};
  const question = (data as any)?.question || "Who are my best customers right now, and who's slipping?";
  const a02ModuleKey = moduleKey || "A02";

  const customers = data?.top_customers || [];
  const segments = data?.segments || [];

  const points = useMemo(() => {
    if (customers.length === 0) return [];
    const sample = customers.slice(0, 600);
    const maxRecency = Math.max(...sample.map((c) => c.recency_days ?? 1), 1);
    const maxFrequency = Math.max(...sample.map((c) => c.frequency ?? 1), 1);
    const maxMonetary = Math.max(...sample.map((c) => c.monetary ?? 0), 1);
    return sample.map((c) => {
      const recency = c.recency_days ?? 0;
      const x = maxRecency > 0 ? 1 - recency / maxRecency : 0.5;
      const y = Math.log(1 + (c.frequency ?? 1)) / Math.log(1 + maxFrequency);
      const z = Math.log(1 + (c.monetary ?? 0)) / Math.log(1 + maxMonetary);
      return {
        x: +x.toFixed(4),
        y: +y.toFixed(4),
        z: +(z * 700 + 50).toFixed(0),
        recency,
        frequency: c.frequency ?? 0,
        monetary: c.monetary ?? 0,
        segment: c.segment,
        customer_id: c.customer_id,
      };
    });
  }, [customers]);

  const grouped = useMemo(() => {
    const out: Record<string, typeof points> = {};
    points.forEach((p) => {
      (out[p.segment] ||= []).push(p);
    });
    return out;
  }, [points]);

  const legendSegments = useMemo(() => {
    const sorted = (segments || []).slice().sort((a, b) => (b.count || 0) - (a.count || 0));
    const top = sorted.slice(0, 5);
    const rest = sorted.slice(5);
    return { top, rest };
  }, [segments]);

  const totalCustomers = data?.summary?.n_customers ?? customers.length;

  if (points.length === 0) {
    return (
      <DecisionCardShell
        moduleKey={a02ModuleKey}
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="champions identified"
        aiInsight={<AIInsightPanel moduleKey={a02ModuleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={((data as any)?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <div className="w-full h-full flex items-center justify-center text-xs text-slate-400 dark:text-slate-500 p-4">
          No customer data available yet. Upload a CSV with order_date, customer_id, and total_amount.
        </div>
      </DecisionCardShell>
    );
  }

  const championSeg = segments.find((s) => s.segment === "Champions");
  const championCount = championSeg?.count ?? Math.max(0, Math.round(totalCustomers * 0.1));

  // ── Direct-answer summary: count customers in each broad health band ─
  // The question asks "who's best, who's slipping?". This strip answers
  // both in one row of named-and-counted cards. The 3D scatter below is
  // the supporting visual evidence.
  const sumByFamily = (matcher: RegExp): number =>
    segments.reduce((acc, s) => (matcher.test(s.segment) ? acc + (s.count || 0) : acc), 0);
  const championsN = sumByFamily(/champion|loyal|potential.*loyal|promising/i);
  const slippingN = sumByFamily(/at risk|cannot lose|about to sleep|need attention/i);
  const lostN = sumByFamily(/hibernating|lost/i);
  const newN = sumByFamily(/^new customers?$/i);

  const familyCards: Array<{ label: string; n: number; color: string; bg: string }> = [
    { label: "Champions", n: championsN, color: "#10b981", bg: "rgba(16,185,129,0.15)" },
    { label: "New",       n: newN,       color: "#06b6d4", bg: "rgba(6,182,212,0.15)" },
    { label: "Slipping",  n: slippingN,  color: "#f59e0b", bg: "rgba(245,158,11,0.18)" },
    { label: "Lost",      n: lostN,      color: "#e11d48", bg: "rgba(225,29,72,0.18)" },
  ];

  return (
    <DecisionCardShell
      moduleKey={a02ModuleKey}
      question={question}
      period={headline.period || `${totalCustomers.toLocaleString()} customers`}
      headlineValue={String(headline.value ?? championCount)}
      headlineLabel={headline.label || "Champions identified"}
      headlineKind="positive"
      aiInsight={<AIInsightPanel moduleKey={a02ModuleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={((data as any)?.suggested_actions as SuggestedAction[]) || []} />}
    >
      {/* Direct-answer cluster strip — 4 cards naming the families with counts */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        {familyCards.map((f) => (
          <div
            key={f.label}
            className="rounded-md px-2.5 py-2 text-center"
            style={{
              background: f.bg,
              border: `1px solid ${f.color}33`,
              boxShadow: f.n > 0 ? `0 0 0 1px ${f.color}22` : "none",
            }}
            title={`${f.n.toLocaleString()} customers in ${f.label}`}
          >
            <p
              className="text-[9.5px] font-bold uppercase tracking-wider"
              style={{ color: f.color }}
            >
              {f.label}
            </p>
            <p
              className="text-xl font-extrabold tabular-nums leading-none mt-0.5"
              style={{ color: f.color }}
            >
              {f.n.toLocaleString()}
            </p>
          </div>
        ))}
      </div>

      <div className="flex-1 min-h-0 flex flex-col md:flex-row py-2">
        <div className="flex-1 min-h-[300px] p-3">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 14, right: 16, bottom: 30, left: 6 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={theme.gridStroke}
                strokeOpacity={0.6}
              />
              <XAxis
                type="number"
                dataKey="x"
                domain={[0, 1]}
                tick={{ fontSize: 10, fill: theme.axisColor }}
                tickFormatter={(v) =>
                  v === 0 ? "Churned" : v >= 0.95 ? "Recent" : v <= 0.5 ? "Avg" : ""
                }
                tickLine={false}
                axisLine={{ stroke: theme.gridStroke }}
                label={{
                  value: "Recency (Days Since Last Order)",
                  position: "insideBottom",
                  offset: -16,
                  style: { fontSize: 11, fill: theme.axisColor, fontWeight: 600 },
                }}
              />
              <YAxis
                type="number"
                dataKey="y"
                domain={[0, 1]}
                tick={{ fontSize: 10, fill: theme.axisColor }}
                tickFormatter={(v) => (v >= 0.95 ? "High" : v >= 0.45 ? "Med" : "Low")}
                tickLine={false}
                axisLine={{ stroke: theme.gridStroke }}
                label={{
                  value: "Frequency (Orders)",
                  angle: -90,
                  position: "insideLeft",
                  offset: 8,
                  style: { fontSize: 11, fill: theme.axisColor, fontWeight: 600, textAnchor: "middle" },
                }}
              />
              <ZAxis type="number" dataKey="z" range={[50, 750]} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                contentStyle={{
                  background: theme.tooltip.background,
                  border: `1px solid ${theme.tooltip.borderColor}`,
                  borderRadius: 8,
                  boxShadow: "0 4px 12px rgba(15,23,42,0.08)",
                  fontSize: 12,
                  padding: 8,
                  color: theme.tooltip.color,
                }}
                itemStyle={{ color: theme.tooltip.color }}
                formatter={(_v: any, name: string, item: any) => {
                  if (!item?.payload) return ["", name];
                  const p = item.payload;
                  if (name === "x") return [`${p.recency} days`, "Recency"];
                  if (name === "y") return [`${p.frequency.toLocaleString()} orders`, "Frequency"];
                  if (name === "z") return [formatMoney(p.monetary, currency, { exact: true, decimals: 0, from: sourceCurrency }), "Monetary"];
                  return [_v, name];
                }}
                labelFormatter={(_l, payload: any) => {
                  const p = payload?.[0]?.payload;
                  return p ? `${p.segment} — ${(p.customer_id || "").slice(0, 12)}…` : "";
                }}
              />
              {Object.entries(grouped).map(([segment, pts]) => {
                const viz = SEGMENT_FAMILY[segment] || DEFAULT_VIZ;
                return (
                  <Scatter
                    key={segment}
                    name={segment}
                    data={pts}
                    fill={viz.color}
                    fillOpacity={0.65}
                    stroke="var(--surface-card, #ffffff)"
                    strokeWidth={1}
                    className="transition-opacity hover:opacity-100"
                  />
                );
              })}
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        <aside className="w-full md:w-60 flex-shrink-0 p-4 bg-slate-50/50 dark:bg-white/[0.02] rounded-xl border border-slate-100 dark:border-white/5 flex flex-col gap-5 overflow-y-auto mt-4 md:mt-0 md:ml-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2">
              <span className="w-1 h-3 rounded-sm bg-blue-500" /> Segments
            </p>
            <ul className="flex flex-col gap-4">
              {legendSegments.top.map((s) => {
                const viz = SEGMENT_FAMILY[s.segment] || DEFAULT_VIZ;
                return (
                  <li key={s.segment} className="flex items-start gap-3">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0 mt-1 shadow-sm"
                      style={{ background: viz.color }}
                    />
                    <div>
                      <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                        {s.segment}
                        <span className="ms-1.5 text-[10px] text-slate-400 font-medium bg-slate-100 dark:bg-white/5 px-1.5 py-0.5 rounded">
                          {s.count.toLocaleString()}
                        </span>
                      </p>
                      <p className="text-[10px] text-slate-500 leading-snug mt-1 font-medium">
                        {viz.blurb}
                      </p>
                    </div>
                  </li>
                );
              })}
              {legendSegments.rest.length > 0 && (
                <li className="pt-3 mt-1 border-t border-slate-100 dark:border-white/5">
                  {legendSegments.rest.map((s) => {
                    const viz = SEGMENT_FAMILY[s.segment] || DEFAULT_VIZ;
                    return (
                      <div key={s.segment} className="flex items-center gap-2 mb-2 last:mb-0">
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ background: viz.color }}
                        />
                        <span className="text-[11px] font-medium text-slate-600 dark:text-slate-300 flex-1">
                          {s.segment}
                        </span>
                        <span className="text-[10px] font-bold text-slate-400">{s.count.toLocaleString()}</span>
                      </div>
                    );
                  })}
                </li>
              )}
            </ul>
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-white/5 mt-auto">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">
              Volume Indicator
            </p>
            <div className="flex items-center gap-3 bg-white dark:bg-surface-elevated p-2 rounded-lg border border-slate-100 dark:border-white/5">
              <div className="flex items-end gap-1">
                <span className="w-2 h-2 rounded-full bg-slate-200 dark:bg-white/10" />
                <span className="w-3 h-3 rounded-full bg-slate-300 dark:bg-white/20" />
                <span className="w-4 h-4 rounded-full bg-slate-400 dark:bg-white/30" />
              </div>
              <p className="text-[10px] font-medium text-slate-500 leading-tight">
                Bubble size represents total Monetary Value
              </p>
            </div>
          </div>
        </aside>
      </div>
    </DecisionCardShell>
  );
}
