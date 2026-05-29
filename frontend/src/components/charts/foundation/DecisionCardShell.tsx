"use client";

/**
 * <DecisionCardShell> — the 6-zone card every "decision chart" wraps with.
 *
 *   ┌─────────────────────────────────────────────────────┐
 *   │ Q: <one owner-voice question>           [period ⌄]  │ 1. Question header
 *   ├─────────────────────────────────────────────────────┤
 *   │ <big headline number>     <trend badge>             │ 2. Headline strip
 *   ├─────────────────────────────────────────────────────┤
 *   │                                                     │
 *   │           <children — the actual visual>            │ 3. Visual evidence
 *   │                                                     │
 *   ├─────────────────────────────────────────────────────┤
 *   │ ✨ AI Insight — 3 bullets                           │ 4. AI insight slot
 *   ├─────────────────────────────────────────────────────┤
 *   │ [→ Action 1]  [→ Action 2]      module_key · scope  │ 5. Actions + 6. footer
 *   └─────────────────────────────────────────────────────┘
 *
 * Every chart that adopts the new design system MUST use this shell. That's
 * what makes the dark/light parity, the question framing, and the AI slot
 * uniform across all 39 modules.
 */

import { ReactNode } from "react";
import { ChevronDown } from "lucide-react";

import { useChartTheme, type SemanticKind } from "../chartHelpers";
import { TrendBadge } from "../chartHelpers";

export interface DecisionCardShellProps {
  /** The owner-voice question this chart answers. */
  question: string;
  /** Module key used as the metadata footer tag (e.g. "A14"). */
  moduleKey: string;
  /** Period label shown in the header dropdown (e.g. "Last 30 days"). */
  period?: string;
  /** Big headline number — render however you like (string or formatted node). */
  headlineValue: ReactNode;
  /** Small label under the headline (e.g. "new customers"). */
  headlineLabel?: string;
  /** Trend percentage vs comparison period. Positive = up. */
  trendPct?: number | null;
  /** Period the trend is compared against ("vs last 30d", "vs target"). */
  trendPeriod?: string;
  /** Optional sentiment override for the headline value tint. */
  headlineKind?: SemanticKind;
  /** Slot: the chart itself. Renders inside the visual zone. */
  children: ReactNode;
  /** Slot: <AIInsightPanel> instance. Renders in zone 4. */
  aiInsight?: ReactNode;
  /** Slot: <ActionChipRow> instance. Renders in zone 5. */
  actions?: ReactNode;
  /** Override className on the outer card. */
  className?: string;
  /** Optional extra controls in the header (e.g. tabs). */
  headerRight?: ReactNode;
}

export function DecisionCardShell({
  question,
  moduleKey,
  period,
  headlineValue,
  headlineLabel,
  trendPct,
  trendPeriod,
  headlineKind,
  children,
  aiInsight,
  actions,
  className = "",
  headerRight,
}: DecisionCardShellProps) {
  const t = useChartTheme();

  const headlineColor =
    headlineKind && headlineKind !== "neutral"
      ? t.semantic[headlineKind]
      : t.text.headline;

  return (
    <div
      className={`w-full h-full flex flex-col rounded-xl overflow-hidden border transition-shadow ${className}`}
      style={{
        background: t.surface,
        borderColor: t.border,
        boxShadow: t.isDark
          ? "0 1px 0 rgba(255,255,255,0.04) inset, 0 1px 3px rgba(0,0,0,0.40)"
          : "0 1px 3px rgba(15,23,42,0.06)",
      }}
    >
      {/* ── Zone 1 · Question header ─────────────────────────────── */}
      <div
        className="px-5 pt-4 pb-3 flex items-start justify-between gap-3 border-b"
        style={{ borderColor: t.border }}
      >
        <div className="min-w-0 flex-1">
          <p
            className="text-[10px] font-bold uppercase tracking-wider mb-1"
            style={{ color: t.text.faint }}
          >
            The Question
          </p>
          <h3
            className="text-[13px] leading-snug font-semibold"
            style={{ color: t.text.headline }}
          >
            {question}
          </h3>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {headerRight}
          {period && (
            <div
              className="text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded-md inline-flex items-center gap-1"
              style={{
                background: t.surfaceMuted,
                color: t.text.muted,
                border: `1px solid ${t.border}`,
              }}
            >
              {period}
              <ChevronDown className="w-3 h-3" />
            </div>
          )}
        </div>
      </div>

      {/* ── Zone 2 · Headline strip ──────────────────────────────── */}
      <div className="px-5 pt-4 pb-3 flex items-end justify-between gap-3 shrink-0">
        <div className="min-w-0">
          <div
            className="text-[28px] leading-none font-extrabold tracking-tight"
            style={{ color: headlineColor }}
          >
            {headlineValue}
          </div>
          {headlineLabel && (
            <p
              className="text-[11px] mt-1.5 font-medium"
              style={{ color: t.text.muted }}
            >
              {headlineLabel}
            </p>
          )}
        </div>
        {trendPct != null && (
          <div className="flex flex-col items-end gap-0.5 shrink-0">
            <TrendBadge value={trendPct} />
            {trendPeriod && (
              <span className="text-[9.5px]" style={{ color: t.text.faint }}>
                {trendPeriod}
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── Zone 3 · Visual ──────────────────────────────────────── */}
      {/* flex flex-col lets direct children use flex-1 to fill the
          remaining card height — critical so charts expand when the
          user resizes a widget in customisation mode. */}
      <div className="flex-1 min-h-0 flex flex-col px-5 pb-3 relative">{children}</div>

      {/* ── Zone 4 · AI Insight ──────────────────────────────────── */}
      {aiInsight && <div className="px-5 pb-3">{aiInsight}</div>}

      {/* ── Zone 5/6 · Actions row + metadata footer ─────────────── */}
      <div
        className="px-5 py-3 border-t flex items-center justify-between gap-3 shrink-0"
        style={{ borderColor: t.border, background: t.surfaceMuted }}
      >
        <div className="flex-1 min-w-0">{actions}</div>
        <span
          className="text-[9px] font-semibold uppercase tracking-wider shrink-0 px-2 py-0.5 rounded"
          style={{
            color: t.text.faint,
            background: t.surface,
            border: `1px solid ${t.border}`,
          }}
        >
          {moduleKey}
        </span>
      </div>
    </div>
  );
}
