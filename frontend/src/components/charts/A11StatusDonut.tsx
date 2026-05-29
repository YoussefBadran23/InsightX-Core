"use client";

/**
 * A11 — Order Status Distribution · Decision-Chart v1.
 *
 * Question answered: "How many orders are stuck and need my attention right now?"
 *
 * Visual (zone 3): "Stuck orders" list. Every row IS an order status that's
 * blocking revenue (in_progress / failure), sorted by count desc, with a
 * coloured pill so the eye lands on the most painful one first. Completed
 * orders are shown as a single muted footer line so the visual doesn't
 * spend pixels on the "good" answer — it spends them on the question
 * (what needs attention?).
 */

import { useMemo } from "react";
import { AlertTriangle, XCircle, CheckCircle2 } from "lucide-react";

import { useChartTheme, fmtCompact } from "./chartHelpers";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";

interface StatusRow {
  status: string;
  count: number;
  pct: number;
  category: "success" | "in_progress" | "failure" | "unknown";
}

interface A11Data {
  question?: string;
  headline?: {
    value?: number; label?: string;
    trend_pct?: number | null;
    period?: string;
  };
  summary?: {
    n_orders?: number;
    success_rate_pct?: number;
    cancellation_rate_pct?: number;
    refund_rate_pct?: number;
    in_progress_pct?: number;
  };
  by_status?: StatusRow[];
  fallback_bullets?: string[];
  suggested_actions?: SuggestedAction[];
}

export function A11StatusDonut({ data, moduleKey }: { data: A11Data; moduleKey: string }) {
  const theme = useChartTheme();
  const rows = data?.by_status || [];
  const summary = data?.summary || {};
  const headline = data?.headline ?? {};
  const question = data?.question || "How many orders are stuck and need my attention right now?";

  // Categorize each row. Worker provides `category` already, but fall back to
  // keyword matching on the raw status name so we never mislabel.
  const { stuck, successN, total } = useMemo(() => {
    const matches = (s: string, kws: RegExp) => kws.test((s || "").toLowerCase());
    const stuckRows: Array<StatusRow & { kind: "in_progress" | "failure" }> = [];
    let s = 0;
    let totalN = 0;
    rows.forEach((r) => {
      const cat = r.category;
      const status = String(r.status || "");
      const n = Number(r.count) || 0;
      totalN += n;
      if (cat === "success" || matches(status, /(deliver|complete|fulfilled|ship|paid)/)) {
        s += n;
        return;
      }
      if (cat === "failure" || matches(status, /(cancel|fail|refund|reject|void|return|charge)/)) {
        stuckRows.push({ ...r, kind: "failure" });
        return;
      }
      if (cat === "in_progress" || matches(status, /(process|pend|wait|hold|invoic|ready|packed|transit|open|new|placed|approved)/)) {
        stuckRows.push({ ...r, kind: "in_progress" });
        return;
      }
      s += n;
    });
    stuckRows.sort((a, b) => b.count - a.count);
    return { stuck: stuckRows, successN: s, total: totalN };
  }, [rows]);

  const needsAttention =
    Number(headline.value ?? stuck.reduce((acc, r) => acc + r.count, 0));
  const successPct = total > 0 ? (successN / total) * 100 : 0;
  const cancelPct = Number(summary.cancellation_rate_pct ?? 0);
  const refundPct = Number(summary.refund_rate_pct ?? 0);

  // Order the list with FAILURES first (they're more urgent than in_progress).
  const visibleStuck = useMemo(() => {
    const failures = stuck.filter((r) => r.kind === "failure");
    const progress = stuck.filter((r) => r.kind === "in_progress");
    return [...failures, ...progress].slice(0, 6);
  }, [stuck]);

  return (
    <DecisionCardShell
      moduleKey="A11"
      question={question}
      period={headline.period || "Right now"}
      headlineValue={fmtCompact(needsAttention, 0)}
      headlineLabel={headline.label || "orders need attention"}
      trendPct={null}
      headlineKind={
        needsAttention === 0 ? "positive" :
        cancelPct + refundPct >= 5 ? "danger" : "warning"
      }
      aiInsight={
        <AIInsightPanel
          moduleKey={moduleKey}
          question={question}
          data={data}
        />
      }
      actions={
        <ActionChipRow
          actions={data?.suggested_actions || []}
          onAction={(a) => {
            // eslint-disable-next-line no-console
            console.log("A11 action click:", a);
          }}
        />
      }
    >
      {total === 0 ? (
        <div
          className="w-full h-full min-h-[180px] flex items-center justify-center text-xs"
          style={{ color: theme.text.muted }}
        >
          No order status data yet.
        </div>
      ) : needsAttention === 0 ? (
        // ── All-clear state ───────────────────────────────────────────────
        // No stuck orders — the visual answer is "you're caught up", carried
        // by a single calm green block instead of an empty list.
        <div
          className="w-full h-full min-h-[180px] flex flex-col items-center justify-center gap-2 rounded-lg"
          style={{
            background: theme.semanticSoft.positive,
            border: `1px solid ${theme.semantic.positive}33`,
          }}
        >
          <CheckCircle2 className="w-8 h-8" style={{ color: theme.semantic.positive }} />
          <p className="text-sm font-bold" style={{ color: theme.semantic.positive }}>
            All orders are flowing
          </p>
          <p className="text-[11px]" style={{ color: theme.text.muted }}>
            {fmtCompact(total, 0)} orders · 100% completed
          </p>
        </div>
      ) : (
        // ── Stuck orders list — the visual answer ────────────────────────
        //
        // Each row is a status that's blocking revenue. The list IS the
        // answer to "how many need my attention right now?" — the headline
        // tells you the total, the list tells you what each kind is and
        // (most importantly) which is biggest.
        <div className="w-full h-full flex flex-col gap-2 pt-1">
          <div
            className="text-[10px] font-bold uppercase tracking-wider px-1"
            style={{ color: theme.text.faint }}
          >
            Stuck Orders · ranked by count
          </div>
          <ul className="space-y-1.5 flex-1 min-h-0 overflow-hidden">
            {visibleStuck.map((r) => {
              const isFailure = r.kind === "failure";
              const color = isFailure ? theme.semantic.danger : theme.semantic.warning;
              const bg = isFailure ? theme.semanticSoft.danger : theme.semanticSoft.warning;
              const Icon = isFailure ? XCircle : AlertTriangle;
              const pctOfTotal = total > 0 ? (r.count / total) * 100 : 0;
              return (
                <li
                  key={r.status}
                  className="rounded-lg px-3 py-2 transition-colors flex items-center gap-3"
                  style={{
                    background: bg,
                    border: `1px solid ${color}44`,
                    boxShadow: `0 0 0 1px ${color}1a`,
                  }}
                >
                  <Icon
                    className="w-4 h-4 shrink-0"
                    style={{ color }}
                  />
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-[12px] font-semibold capitalize truncate"
                      style={{ color: theme.text.headline }}
                    >
                      {String(r.status).toLowerCase().replace(/_/g, " ")}
                    </p>
                    <p
                      className="text-[10px] font-medium uppercase tracking-wider"
                      style={{ color }}
                    >
                      {isFailure ? "Needs recovery" : "Awaiting action"}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p
                      className="text-[15px] font-extrabold tabular-nums leading-none"
                      style={{ color }}
                    >
                      {fmtCompact(r.count, 0)}
                    </p>
                    <p
                      className="text-[10px] tabular-nums mt-0.5"
                      style={{ color: theme.text.faint }}
                    >
                      {pctOfTotal.toFixed(1)}% of all
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>

          {/* Completed-orders muted footer — frames the "ok" baseline so the
              list above reads as "this is what's wrong" rather than "this is
              all the data". */}
          <div
            className="flex items-center justify-between gap-2 text-[10.5px] pt-1.5 border-t"
            style={{ borderColor: theme.border, color: theme.text.muted }}
          >
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3 h-3" style={{ color: theme.semantic.positive }} />
              {fmtCompact(successN, 0)} completed
            </span>
            <span style={{ color: theme.text.faint }}>
              {successPct.toFixed(1)}% of {fmtCompact(total, 0)} orders
            </span>
          </div>
        </div>
      )}
    </DecisionCardShell>
  );
}
