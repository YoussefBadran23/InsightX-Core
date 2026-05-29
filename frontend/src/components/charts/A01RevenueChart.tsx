"use client";

/**
 * A01 — Revenue Trends · Decision-Chart v1.
 *
 * Question answered: "How much money did I make, and is it more or less than before?"
 *
 * Visual zone: current period vs previous period composed chart (solid brand
 * line + soft gradient fill for current, dashed slate line for previous).
 *
 * Wraps with `DecisionCardShell` so the user sees the owner-voice question,
 * the headline number, 3 AI-generated bullets, and recommended actions —
 * not just the chart.
 */

import { useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

import { useAuthStore } from "@/stores/authStore";
import { useJobStore } from "@/stores/jobStore";
import { formatMoney } from "@/lib/format";
import { fmtCompact, useChartTheme } from "./chartHelpers";
import { InsightTooltip } from "./foundation/InsightTooltip";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";

interface PeriodBucket {
  label: string;
  month: string;
  current: number;
  previous: number | null;
}

interface A01Data {
  question?: string;
  headline?: {
    value?: number; label?: string;
    trend_pct?: number | null;
    trend_direction?: "up" | "down" | "flat" | null;
    period?: string;
  };
  period_comparison?: {
    buckets: PeriodBucket[];
    current_total: number;
    previous_total: number;
    change_pct: number | null;
  };
  by_period?: {
    monthly?: Array<{ period: string; revenue: number; orders: number }>;
  };
  fallback_bullets?: string[];
  suggested_actions?: SuggestedAction[];
}

interface Props {
  data: A01Data;
  moduleKey: string;
}

export function A01RevenueChart({ data, moduleKey }: Props) {
  const theme = useChartTheme();
  const currency = useAuthStore((s) => s.user?.preferred_currency) || "USD";
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);

  const chartData = useMemo(() => {
    const pc = data?.period_comparison;
    if (pc?.buckets?.length) {
      return pc.buckets.map((b) => ({
        label: b.label,
        current: Number(b.current) || 0,
        previous: b.previous == null ? null : Number(b.previous) || 0,
      }));
    }
    const monthly = data?.by_period?.monthly || [];
    return monthly.slice(-6).map((r) => ({
      label: r.period,
      current: Number(r.revenue) || 0,
      previous: null,
    }));
  }, [data]);

  const pc = data?.period_comparison;
  const headline = data?.headline ?? {};
  const question = data?.question || "How much money did I make, and is it more or less than before?";

  const headlineValue = (() => {
    const v = headline.value ?? pc?.current_total ?? 0;
    return formatMoney(v, currency, { from: sourceCurrency });
  })();

  const fmt = (v: number) => formatMoney(v, currency, { from: sourceCurrency });

  return (
    <DecisionCardShell
      moduleKey="A01"
      question={question}
      period={headline.period || "Last 6 months"}
      headlineValue={headlineValue}
      headlineLabel={headline.label || "revenue · current period"}
      trendPct={headline.trend_pct ?? pc?.change_pct ?? null}
      trendPeriod={
        (headline.trend_pct ?? pc?.change_pct) != null
          ? "vs prior 6 months"
          : undefined
      }
      headlineKind={
        (headline.trend_pct ?? pc?.change_pct ?? 0) >= 0 ? "positive" : "warning"
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
            console.log("A01 action click:", a);
          }}
        />
      }
    >
      {chartData.length === 0 ? (
        <div
          className="w-full h-full min-h-[180px] flex items-center justify-center text-xs"
          style={{ color: theme.text.muted }}
        >
          No revenue data available yet.
        </div>
      ) : (
        <div className="w-full h-full min-h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 8, right: 6, left: -8, bottom: 0 }}>
              <defs>
                <linearGradient id="a01-current-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={theme.semantic.brand} stopOpacity={0.42} />
                  <stop offset="55%" stopColor={theme.semantic.brand} stopOpacity={0.16} />
                  <stop offset="95%" stopColor={theme.semantic.brand} stopOpacity={0} />
                </linearGradient>
                <filter id="a01-glow" x="-15%" y="-30%" width="130%" height="170%">
                  <feGaussianBlur stdDeviation={theme.isDark ? 3 : 2} result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke={theme.gridStroke}
                strokeOpacity={0.6}
              />

              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: theme.text.muted }}
                tickLine={false}
                axisLine={false}
                minTickGap={8}
              />
              <YAxis
                tick={{ fontSize: 10, fill: theme.text.muted }}
                tickLine={false}
                axisLine={false}
                width={50}
                tickFormatter={(v) => fmt(Number(v))}
              />

              <Tooltip content={<InsightTooltip currency={currency} sourceCurrency={sourceCurrency} />} />

              <Line
                type="monotone"
                dataKey="previous"
                name="Previous Period"
                stroke={theme.text.faint}
                strokeWidth={2}
                strokeDasharray="6 4"
                dot={false}
                isAnimationActive={true}
                connectNulls={false}
              />

              <Area
                type="monotone"
                dataKey="current"
                name="Current Period"
                stroke={theme.semantic.brand}
                strokeWidth={3}
                fill="url(#a01-current-fill)"
                filter="url(#a01-glow)"
                activeDot={{
                  r: 6, strokeWidth: 2,
                  stroke: theme.surface,
                  fill: theme.semantic.brand,
                }}
                isAnimationActive={true}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </DecisionCardShell>
  );
}

// Avoid unused-import warnings when fmtCompact is removed downstream.
void fmtCompact;
