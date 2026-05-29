"use client";

/**
 * Shared utilities for all chart components.
 *
 * Keeps formatters, palettes, and tiny presentational atoms in one place so
 * every chart renders consistently (same compact-number style, same series
 * colours, same empty-state).
 */

import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { useUiStore } from "@/stores/uiStore";

/** Compact number formatting: 1.2M, 47.3k, 950 */
export function fmtCompact(n: number | null | undefined, decimals = 1): string {
  if (n == null || isNaN(n)) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(decimals)}B`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(decimals)}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(decimals)}k`;
  return `${sign}${abs.toFixed(decimals === 0 ? 0 : Math.min(decimals, 2))}`;
}

/** Percent formatter for tooltips/axes. */
export function fmtPct(n: number | null | undefined, decimals = 2): string {
  if (n == null || isNaN(n)) return "—";
  return `${n.toFixed(decimals)}%`;
}

/** Truncate string with ellipsis */
export function truncate(s: string | null | undefined, max = 24): string {
  if (!s) return "";
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

/**
 * Canonical 12-colour series palette used wherever a chart needs to colour
 * unrelated categories. Chosen for legibility on both light and dark themes.
 */
export const PALETTE = [
  "#137fec", // blue (primary)
  "#22c55e", // green
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#ec4899", // pink
  "#10b981", // emerald
  "#f97316", // orange
  "#3b82f6", // blue-500
  "#84cc16", // lime
  "#a855f7", // purple
];

/** Diverging palette for heatmaps (low → high) */
export const HEAT_PALETTE = [
  "#dbeafe", // very light blue
  "#bfdbfe",
  "#93c5fd",
  "#60a5fa",
  "#3b82f6",
  "#2563eb",
  "#1d4ed8", // dark blue
];

/** Pick a palette colour by index (cycles modulo). */
export function paletteColor(idx: number): string {
  return PALETTE[idx % PALETTE.length];
}

/** Sentiment / health colour by qualitative state. */
export const STATE_COLORS = {
  positive: "#22c55e",
  negative: "#ef4444",
  neutral: "#94a3b8",
  warning: "#f59e0b",
  info: "#137fec",
};

/** Map a value in [vMin, vMax] to a HEAT_PALETTE colour. */
export function heatColor(v: number, vMin: number, vMax: number): string {
  if (vMax === vMin) return HEAT_PALETTE[0];
  const t = Math.max(0, Math.min(1, (v - vMin) / (vMax - vMin)));
  const idx = Math.min(HEAT_PALETTE.length - 1, Math.floor(t * HEAT_PALETTE.length));
  return HEAT_PALETTE[idx];
}

/** Inline empty / no-data state for any chart. */
export function NoDataState({ message = "No data" }: { message?: string }) {
  return (
    <div className="w-full h-full flex items-center justify-center text-slate-400 text-xs p-4 text-center">
      {message}
    </div>
  );
}

/** Inline trend indicator: ↑ green / ↓ red / – grey */
export function TrendBadge({ value, suffix = "%" }: { value: number | null | undefined; suffix?: string }) {
  if (value == null || isNaN(value)) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-slate-400">
        <Minus className="w-3 h-3" /> —
      </span>
    );
  }
  if (value > 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-emerald-600 dark:text-emerald-400">
        <TrendingUp className="w-3 h-3" />
        +{value.toFixed(1)}{suffix}
      </span>
    );
  }
  if (value < 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-red-600 dark:text-red-400">
        <TrendingDown className="w-3 h-3" />
        {value.toFixed(1)}{suffix}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs text-slate-400">
      <Minus className="w-3 h-3" />
      0{suffix}
    </span>
  );
}

/** Common Recharts tooltip style (light theme; dark mode hooks via Tailwind). */
export const TOOLTIP_STYLE = {
  borderRadius: 8,
  fontSize: 11,
  border: "1px solid rgba(148, 163, 184, 0.3)",
  backgroundColor: "rgba(255,255,255,0.96)",
} as const;

/**
 * Semantic kind — used by AI Insight panel, action chips, and headline trends
 * to pick a consistent colour without each call site hard-coding hex literals.
 */
export type SemanticKind = "brand" | "positive" | "warning" | "danger" | "info" | "neutral";

/**
 * Theme-aware chart config used by every chart to guarantee dark/light parity.
 *
 * Returns three groups of tokens:
 *   - Surface/text/border  — for the card shell + zones around the chart
 *   - Chart-specific       — grid, axis, tooltip, glow filter
 *   - Semantic accents     — brand/positive/warning/danger/info/neutral
 *
 * Backward-compatible: keeps the original `primary`, `gridStroke`, `axisColor`,
 * `tooltip`, `cardBg`, `cardBorder`, `glowFilter`, `isDark` keys so existing
 * charts don't have to be refactored in one shot.
 */
export function useChartTheme() {
  const isDark = useUiStore((s) => s.theme === "dark");

  // Surface (card chrome)
  const surface = isDark ? "#181B23" : "#FFFFFF";
  const surfaceMuted = isDark ? "#1F232E" : "#F8FAFC";
  const border = isDark ? "#2A2E3A" : "#E2E8F0";
  const borderStrong = isDark ? "#3A3F4D" : "#CBD5E1";
  const ring = isDark ? "rgba(178,197,255,0.15)" : "rgba(0,83,205,0.10)";

  // Text
  const textHeadline = isDark ? "#FFFFFF" : "#0F172A";
  const textBody = isDark ? "#E2E8F0" : "#1E293B";
  const textMuted = isDark ? "#94A3B8" : "#64748B";
  const textFaint = isDark ? "#64748B" : "#94A3B8";

  // Semantic accents — lifted in dark for contrast, deeper in light
  const semantic = {
    brand:    isDark ? "#2B6CEE" : "#0053CD",
    positive: isDark ? "#10B981" : "#059669",
    warning:  isDark ? "#F59E0B" : "#D97706",
    danger:   isDark ? "#EF4444" : "#DC2626",
    info:     isDark ? "#06B6D4" : "#0891B2",
    neutral:  isDark ? "#94A3B8" : "#64748B",
  } satisfies Record<SemanticKind, string>;

  // Soft tints (10% alpha) for backgrounds — used by chips, AI panel bg, etc.
  const semanticSoft = {
    brand:    isDark ? "rgba(43,108,238,0.18)" : "rgba(0,83,205,0.10)",
    positive: isDark ? "rgba(16,185,129,0.18)" : "rgba(5,150,105,0.10)",
    warning:  isDark ? "rgba(245,158,11,0.20)" : "rgba(217,119,6,0.10)",
    danger:   isDark ? "rgba(239,68,68,0.20)" : "rgba(220,38,38,0.10)",
    info:     isDark ? "rgba(6,182,212,0.18)" : "rgba(8,145,178,0.10)",
    neutral:  isDark ? "rgba(148,163,184,0.18)" : "rgba(100,116,139,0.10)",
  } satisfies Record<SemanticKind, string>;

  // Chart-internal
  const gridStroke = isDark ? "rgba(255,255,255,0.06)" : "#F1F5F9";
  const gridStrokeStrong = isDark ? "rgba(255,255,255,0.12)" : "#E2E8F0";
  const axisColor = textMuted;
  const tooltip = {
    background: isDark ? "#1A1D27" : "#FFFFFF",
    borderColor: isDark ? "rgba(255,255,255,0.10)" : "#E2E8F0",
    color: isDark ? "#FAF8FF" : "#0F172A",
    borderRadius: 8,
    fontSize: 12,
  } as const;

  const glowFilter = isDark
    ? "drop-shadow(0 0 4px rgba(178,197,255,0.5))"
    : "none";

  return {
    isDark,

    // ── New semantic API ────────────────────────────────────────────────
    surface,
    surfaceMuted,
    border,
    borderStrong,
    ring,
    text: { headline: textHeadline, body: textBody, muted: textMuted, faint: textFaint },
    semantic,
    semanticSoft,
    gridStrokeStrong,

    /** Pick a semantic colour by kind, with neutral as fallback. */
    semanticColor(kind: SemanticKind | undefined | null): string {
      if (!kind || !(kind in semantic)) return semantic.neutral;
      return semantic[kind];
    },

    // ── Backward-compatible keys (existing charts) ─────────────────────
    primary: semantic.brand,
    gridStroke,
    axisColor,
    tooltip,
    cardBg: surface,
    cardBorder: border,
    glowFilter,
  };
}
