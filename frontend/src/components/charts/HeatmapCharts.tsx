"use client";

/**
 * Heatmap charts. We build these as a CSS grid of cells rather than a
 * chart-lib component because Recharts has no native heatmap and the cell
 * counts are small (≤24×24 for cohort retention).
 *
 *   A05 Cohort Retention — cohort × month_offset
 *   P06 Product Return Heatmap — category × month
 */

import { useMemo } from "react";
import { heatColor, NoDataState } from "./chartHelpers";
import { InsightCard } from "./foundation/InsightCard";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";

interface CohortRow {
  cohort: string;
  size: number;
  retention: Array<{ month_offset: number; active: number; rate: number | null }>;
}

/* ── A05 Cohort Retention · Decision-Chart v1 ───────────────────────────
   Question: "Of the customers who bought last month, how many came back?" */
export function A05CohortRetentionChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const matrix: CohortRow[] = data?.cohort_matrix || [];
  const headline = data?.headline ?? {};
  const question = data?.question || "Of the customers who bought last month, how many came back?";

  const maxOffset = useMemo(() => {
    if (matrix.length === 0) return 0;
    const all = matrix.flatMap((c) => c.retention.map((r) => r.month_offset));
    return Math.min(12, Math.max(...all, 0));
  }, [matrix]);

  if (matrix.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A05"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="month-1 retention"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState message="No cohort data yet." />
      </DecisionCardShell>
    );
  }

  const offsets = Array.from({ length: maxOffset + 1 }, (_, i) => i);

  const cellStyle = (rate: number) => {
    if (rate >= 80) return { background: "var(--primary)", color: "#ffffff" };
    if (rate >= 60) return { background: "rgba(var(--primary-rgb), 0.80)", color: "#ffffff" };
    if (rate >= 40) return { background: "rgba(var(--primary-rgb), 0.55)", color: "#ffffff" };
    if (rate >= 20) return { background: "rgba(var(--primary-rgb), 0.30)", color: "#1e293b" };
    if (rate > 0)   return { background: "rgba(var(--primary-rgb), 0.12)", color: "#475569" };
    return            { background: "var(--surface-elevated, #f8fafc)", color: "#94a3b8" };
  };

  const m1Rate = Number(headline.value ?? data?.summary?.avg_retention_m1 ?? 0);

  return (
    <DecisionCardShell
      moduleKey="A05"
      question={question}
      period={headline.period || `${matrix.length} cohorts tracked`}
      headlineValue={`${m1Rate.toFixed(1)}%`}
      headlineLabel={headline.label || "month-1 retention"}
      headlineKind={m1Rate >= 30 ? "positive" : m1Rate >= 15 ? "neutral" : "warning"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      {/* ── Direct-answer callout · the latest cohort gets called out ─────
          The question says "of LAST MONTH'S customers, how many came
          back?". The heatmap shows the pattern but the user wants the
          answer for the freshest cohort. Surface it as a visible callout
          and highlight the latest row in the heatmap below. */}
      {(() => {
        const latest = matrix[matrix.length - 1];
        if (!latest) return null;
        const latestM1 = latest.retention.find((r) => r.month_offset === 1);
        const latestRate = latestM1?.rate;
        if (latestRate == null) return null;
        const kind = latestRate >= 30 ? "positive" : latestRate >= 15 ? "neutral" : "warning";
        const color = kind === "positive" ? "#10b981" : kind === "warning" ? "#f59e0b" : "#94a3b8";
        const bg = kind === "positive"
          ? "rgba(16,185,129,0.15)"
          : kind === "warning"
            ? "rgba(245,158,11,0.18)"
            : "rgba(148,163,184,0.12)";
        return (
          <div
            className="mb-3 rounded-md px-3 py-2 flex items-center justify-between"
            style={{ background: bg, border: `1px solid ${color}44` }}
          >
            <div>
              <p
                className="text-[10px] font-bold uppercase tracking-wider"
                style={{ color }}
              >
                Latest cohort · {latest.cohort}
              </p>
              <p className="text-[11px] font-medium" style={{ color }}>
                {latestM1?.active.toLocaleString() ?? 0} of {latest.size.toLocaleString()} came back in month 1
              </p>
            </div>
            <p
              className="text-2xl font-extrabold tabular-nums leading-none"
              style={{ color }}
            >
              {latestRate.toFixed(1)}%
            </p>
          </div>
        );
      })()}

      <div className="flex-1 min-h-0 overflow-auto py-2">
        <div className="inline-block min-w-full">
          <div className="flex items-end mb-2 pb-1">
            <div className="w-24 flex-shrink-0 text-[10px] font-bold uppercase tracking-wider text-slate-400 text-right pe-3">
              Cohort · Size
            </div>
            {offsets.map((m) => (
              <div key={m} className="w-12 flex-shrink-0 text-center text-[10px] uppercase tracking-wider text-slate-400 font-bold">
                M{m}
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-[3px]">
            {matrix.slice(0, 18).map((c, idx, arr) => {
              const cellMap = new Map(c.retention.map((r) => [r.month_offset, r]));
              const isLatest = idx === arr.length - 1;
              return (
                <div
                  key={c.cohort}
                  className="flex items-center gap-[3px] rounded-md"
                  style={
                    isLatest
                      ? {
                          padding: "2px 4px",
                          background: "rgba(0,83,205,0.06)",
                          boxShadow: "inset 0 0 0 1px rgba(0,83,205,0.35)",
                        }
                      : undefined
                  }
                >
                  <div className="w-24 flex-shrink-0 text-right pe-3 leading-tight">
                    <div
                      className="text-xs font-mono font-semibold"
                      style={{ color: isLatest ? "#0053cd" : undefined }}
                    >
                      {c.cohort}
                      {isLatest && (
                        <span className="ms-1 text-[9px] font-bold uppercase tracking-wider">
                          ← latest
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] font-medium text-slate-500">{c.size.toLocaleString()}</div>
                  </div>
                  {offsets.map((m) => {
                    const cell = cellMap.get(m);
                    if (!cell || cell.rate == null) {
                      return (
                        <div key={m} className="w-12 h-8 flex-shrink-0 flex items-center justify-center rounded-md text-[11px] font-medium text-slate-400 bg-slate-50 dark:bg-white/[0.02]">
                          —
                        </div>
                      );
                    }
                    const style = cellStyle(cell.rate);
                    return (
                      <div
                        key={m}
                        className="w-12 h-8 flex-shrink-0 flex items-center justify-center rounded-md text-[11px] font-bold transition-transform hover:scale-110 hover:z-10 relative cursor-default"
                        style={style}
                        title={`${c.cohort} · M${m}: ${cell.rate.toFixed(1)}% · ${cell.active.toLocaleString()} active`}
                      >
                        {cell.rate.toFixed(0)}%
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </DecisionCardShell>
  );
}

/* ── P06 Return Heatmap · Decision-Chart v1 ─────────────────────────────
   Question: "Which category × period combo has the worst returns?"    */
export function P06ReturnHeatmapChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const cells: Array<{ category: string; period: string; return_rate_pct: number }> = data?.heatmap || [];
  const hotProducts = data?.hot_products || [];
  const headline = data?.headline ?? {};
  const question = data?.question || "Which category × period combo has the worst returns?";
  const overallRate = Number(headline.value ?? data?.summary?.overall_return_rate_pct ?? 0);

  if (cells.length === 0) {
    if (hotProducts.length === 0) {
      return (
        <DecisionCardShell
          moduleKey="P06"
          question={question}
          period="no data"
          headlineValue="—"
          headlineLabel="overall return rate"
          aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
          actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
        >
          <NoDataState message="No return data" />
        </DecisionCardShell>
      );
    }
    const max = Math.max(...hotProducts.map((p: any) => Number(p.return_rate_pct || 0)), 1);
    return (
      <DecisionCardShell
        moduleKey="P06"
        question={question}
        period={headline.period || "All time"}
        headlineValue={`${overallRate.toFixed(1)}%`}
        headlineLabel={headline.label || "overall return rate"}
        headlineKind={overallRate >= 10 ? "danger" : overallRate >= 5 ? "warning" : "positive"}
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <ul className="space-y-1.5 text-[11px] py-2">
          {hotProducts.slice(0, 18).map((p: any) => {
            const v = Number(p.return_rate_pct || 0);
            return (
              <li key={p.product_id || p.name} className="flex items-center gap-3">
                <span className="w-32 font-medium truncate text-slate-700 dark:text-slate-300" title={p.name || p.product_id}>
                  {p.name || p.product_id}
                </span>
                <div className="flex-1 h-2 rounded-full overflow-hidden bg-slate-100 dark:bg-surface-elevated">
                  <div className="h-full rounded-full" style={{ width: `${(v / max) * 100}%`, backgroundColor: heatColor(v, 0, max) }} />
                </div>
                <span className="w-12 text-right font-bold text-slate-600 dark:text-slate-400">{v.toFixed(1)}%</span>
              </li>
            );
          })}
        </ul>
      </DecisionCardShell>
    );
  }

  const periodsSet = new Set(cells.map((c) => c.period));
  const periods = Array.from(periodsSet).sort().slice(-10);
  const categoriesSet = new Set(cells.map((c) => c.category));
  const categories = Array.from(categoriesSet).slice(0, 12);

  const lookup = new Map<string, number>();
  cells.forEach((c) => lookup.set(`${c.category}|${c.period}`, c.return_rate_pct));

  const vMax = Math.max(...cells.map((c) => c.return_rate_pct), 1);

  return (
    <DecisionCardShell
      moduleKey="P06"
      question={question}
      period={headline.period || "Category × month"}
      headlineValue={`${overallRate.toFixed(1)}%`}
      headlineLabel={headline.label || "overall return rate"}
      headlineKind={overallRate >= 10 ? "danger" : overallRate >= 5 ? "warning" : "positive"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="w-full overflow-auto py-2">
        <table className="text-[10px] w-full" style={{ borderCollapse: "separate", borderSpacing: 3 }}>
          <thead>
            <tr>
              <th className="text-left font-bold text-slate-400 uppercase tracking-wider sticky left-0 bg-transparent pr-2">
                Category
              </th>
              {periods.map((p) => (
                <th key={p} className="text-center font-bold text-slate-400 uppercase tracking-wider px-1">{p}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map((cat) => (
              <tr key={cat}>
                <td className="pr-2 font-medium text-slate-700 dark:text-slate-300 sticky left-0 bg-transparent truncate max-w-[120px]" title={cat}>
                  {cat}
                </td>
                {periods.map((p) => {
                  const v = lookup.get(`${cat}|${p}`);
                  if (v == null) return <td key={p} className="bg-slate-50 dark:bg-white/[0.02] rounded-md" />;
                  const bg = heatColor(v, 0, vMax);
                  const textLight = v > vMax / 2;
                  return (
                    <td
                      key={p}
                      className="text-center rounded-md px-1 py-1 font-bold transition-transform hover:scale-110 cursor-default"
                      style={{ backgroundColor: bg, color: textLight ? "#fff" : "#1e293b", boxShadow: `0 2px 4px ${bg}40` }}
                      title={`${cat} · ${p}: ${v.toFixed(1)}%`}
                    >
                      {v.toFixed(0)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DecisionCardShell>
  );
}
