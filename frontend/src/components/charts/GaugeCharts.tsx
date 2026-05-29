"use client";

/**
 * Gauge / single-KPI dial charts for risk-style metrics:
 *   A20 Churn Risk Prediction, P05 Stock Health Dashboard.
 *
 * Recharts doesn't ship a gauge primitive, but a PieChart with a 180° start
 * angle approximates the classic half-circle "speedometer" closely enough.
 */

import { ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { AlertCircle, Clock } from "lucide-react";
import { InsightCard } from "./foundation/InsightCard";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";
import { NoDataState, useChartTheme, fmtCompact } from "./chartHelpers";

interface GaugeProps {
  value: number;       // 0..100
  label: string;
  sublabel?: string;
  invert?: boolean;    // if true, low values are good (e.g. churn risk)
}

function Gauge({ value, label, sublabel, invert = false }: GaugeProps) {
  const theme = useChartTheme();
  const clamped = Math.max(0, Math.min(100, value));
  
  const colorFor = (v: number) => {
    if (invert) {
      if (v < 30) return "#10b981"; // emerald
      if (v < 60) return "#f59e0b"; // amber
      return "#ef4444"; // red
    }
    if (v < 30) return "#ef4444";
    if (v < 60) return "#f59e0b";
    return "#10b981";
  };
  
  const colour = colorFor(clamped);
  const data = [
    { name: "value", value: clamped, fill: colour },
    { name: "rest", value: 100 - clamped, fill: theme.gridStroke },
  ];

  return (
    <div className="relative w-full h-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart margin={{ top: 20, right: 0, left: 0, bottom: 0 }}>
          <Pie
            data={data}
            startAngle={180}
            endAngle={0}
            innerRadius="75%"
            outerRadius="95%"
            paddingAngle={0}
            dataKey="value"
            isAnimationActive={true}
            stroke="none"
          >
            {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-x-0 bottom-8 flex flex-col items-center pointer-events-none">
        <p className="text-4xl font-black tracking-tighter" style={{ color: colour }}>
          {clamped.toFixed(1)}<span className="text-lg font-bold opacity-70 ml-0.5">%</span>
        </p>
        <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mt-1">{label}</p>
        {sublabel && <p className="text-xs text-slate-400 font-medium mt-1">{sublabel}</p>}
      </div>
    </div>
  );
}

/* ── A20 Churn Risk · Decision-Chart v1 ─────────────────────────────────
   Question: "Which of my loyal customers are about to leave me?"

   Visual: top-10 most at-risk customers as a ranked leaderboard. The list IS
   the answer — each row is a real customer the owner can act on (their
   churn probability, how long they've been silent, and how much they've
   spent over their lifetime). Sorted by churn_probability desc; rows with
   probability ≥ 80% glow red to lock the eye on the worst cases first. */
export function A20ChurnChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const theme = useChartTheme();
  const s = data?.summary || {};
  const headline = data?.headline ?? {};
  const question = data?.question || "Which of my loyal customers are about to leave me?";

  const rate = Number(s.avg_churn_risk ?? s.avg_churn_probability ?? s.churn_rate ?? 0);
  const avgRiskPct = rate <= 1 ? rate * 100 : rate;
  const atRiskCount = Number(headline.value ?? 0);
  const hasData = Number.isFinite(rate) && (s.n_customers ?? 0) > 0;

  const topAtRisk: Array<{
    customer_id: string;
    churn_probability: number;
    recency_days: number;
    frequency: number;
    monetary: number;
  }> = (data?.top_at_risk || []).slice(0, 10);

  return (
    <DecisionCardShell
      moduleKey="A20"
      question={question}
      period={headline.period || "Current snapshot"}
      headlineValue={atRiskCount > 0 ? atRiskCount.toLocaleString() : "0"}
      headlineLabel={headline.label || "customers at risk"}
      trendPct={null}
      headlineKind={
        atRiskCount === 0 ? "positive" :
        avgRiskPct >= 50 ? "danger" : "warning"
      }
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
      {!hasData ? (
        <NoDataState />
      ) : topAtRisk.length === 0 ? (
        <div
          className="w-full h-full min-h-[180px] flex items-center justify-center text-[11px]"
          style={{ color: theme.text.muted }}
        >
          No at-risk customers detected.
        </div>
      ) : (
        <div className="w-full h-full flex flex-col gap-2 pt-1">
          <div className="flex items-center justify-between px-1">
            <span
              className="text-[10px] font-bold uppercase tracking-wider"
              style={{ color: theme.text.faint }}
            >
              Top {topAtRisk.length} at-risk · ranked by churn probability
            </span>
            <span
              className="text-[10px] font-semibold tabular-nums"
              style={{ color: theme.text.muted }}
            >
              avg {avgRiskPct.toFixed(0)}% across {fmtCompact(Number(s.n_customers ?? 0), 0)}
            </span>
          </div>
          <ul className="space-y-1 flex-1 min-h-0 overflow-hidden">
            {topAtRisk.map((c, idx) => {
              const probPct = c.churn_probability * 100;
              const isCritical = probPct >= 80;
              const isHigh = probPct >= 50 && probPct < 80;
              const color = isCritical
                ? theme.semantic.danger
                : isHigh
                ? theme.semantic.warning
                : theme.text.muted;
              const bg = isCritical
                ? theme.semanticSoft.danger
                : isHigh
                ? theme.semanticSoft.warning
                : "transparent";
              const barWidth = Math.max(2, Math.min(100, probPct));
              const displayId = String(c.customer_id || "").slice(0, 14);
              return (
                <li
                  key={`${c.customer_id}-${idx}`}
                  className="rounded-md px-2.5 py-1.5"
                  style={{
                    background: bg,
                    border: `1px solid ${isCritical || isHigh ? color + "44" : theme.border}`,
                  }}
                >
                  <div className="flex items-center gap-2.5 mb-1">
                    <span
                      className="text-[10px] font-extrabold w-4 text-center tabular-nums"
                      style={{ color: theme.text.faint }}
                    >
                      {idx + 1}
                    </span>
                    {isCritical && (
                      <AlertCircle className="w-3 h-3 shrink-0" style={{ color }} />
                    )}
                    <span
                      className="text-[11.5px] font-semibold flex-1 truncate font-mono"
                      style={{ color: theme.text.headline }}
                      title={c.customer_id}
                    >
                      {displayId}
                    </span>
                    <span
                      className="text-[12px] font-extrabold tabular-nums shrink-0"
                      style={{ color }}
                    >
                      {probPct.toFixed(0)}%
                    </span>
                  </div>
                  {/* Risk bar — intensity matches the probability */}
                  <div
                    className="w-full h-1 rounded-full overflow-hidden mb-1"
                    style={{ background: theme.surfaceMuted }}
                  >
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${barWidth}%`,
                        background: color,
                        boxShadow: isCritical ? `0 0 6px ${color}80` : "none",
                      }}
                    />
                  </div>
                  {/* Recency · spend strip — gives the owner the "why" */}
                  <div
                    className="flex items-center justify-between text-[9.5px] tabular-nums"
                    style={{ color: theme.text.faint }}
                  >
                    <span className="flex items-center gap-1">
                      <Clock className="w-2.5 h-2.5" />
                      {c.recency_days}d silent
                    </span>
                    <span>
                      {c.frequency} orders · ${fmtCompact(c.monetary, 0)} lifetime
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </DecisionCardShell>
  );
}

/* ── P05 Stock Health · Decision-Chart v1 ───────────────────────────────
   Question: "How healthy is my overall inventory right now?"          */
export function P05StockHealthChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const s = data?.summary || {};
  const total = Number(s.n_products || 0);
  const headline = data?.headline ?? {};
  const question = data?.question || "How healthy is my overall inventory right now?";

  if (total === 0) {
    return (
      <DecisionCardShell
        moduleKey="P05"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="of SKUs in healthy stock"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState />
      </DecisionCardShell>
    );
  }

  const unhealthy = Number(s.out_of_stock_count || 0) + Number(s.low_count || 0);
  const healthScore = ((total - unhealthy) / total) * 100;
  const headlineValue = Number(headline.value ?? healthScore);

  return (
    <DecisionCardShell
      moduleKey="P05"
      question={question}
      period={headline.period || `${total.toLocaleString()} SKUs`}
      headlineValue={`${headlineValue.toFixed(1)}%`}
      headlineLabel={headline.label || "of SKUs in healthy stock"}
      headlineKind={healthScore >= 90 ? "positive" : healthScore >= 75 ? "warning" : "danger"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[160px]">
        <Gauge
          value={healthScore}
          label="Health Score"
          sublabel={`${total.toLocaleString()} SKUs total · ${unhealthy} at risk/out`}
        />
      </div>
    </DecisionCardShell>
  );
}
