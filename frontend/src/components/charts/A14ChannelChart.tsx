"use client";

/**
 * A14 — Acquisition Channel · Decision-Chart v1 (gold-standard reference).
 *
 * Question answered:
 *   "Which marketing channel is bringing me the most customers?"
 *
 * Layout (6 zones, all themed via useChartTheme()):
 *   1. Question header                — DecisionCardShell
 *   2. Headline number + trend        — DecisionCardShell
 *   3. Visual evidence                — ranked-bars leaderboard (this file)
 *   4. AI Insight (3 bullets)         — AIInsightPanel
 *   5. Action chips                   — ActionChipRow
 *   6. Metadata footer (module key)   — DecisionCardShell
 *
 * Data contract — reads these fields from the worker output:
 *   - question, headline {value,label,trend_pct,trend_direction,period}
 *   - by_channel: [{channel, customers, revenue, aov, avg_ltv,
 *                   rev_share_pct, cust_share_pct, rank}]
 *   - summary.best_channel_aov, summary.best_channel_ltv
 *   - fallback_bullets, suggested_actions
 *
 * The chart is the TEMPLATE every other A/C/P module copies — same shell,
 * same AI slot, same action row. Only zone 3 (the visual) is per-chart.
 */

import { useMemo } from "react";
import { paletteColor, useChartTheme, fmtCompact } from "./chartHelpers";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";

// Channel-palette anchors so common channels keep their identity colours.
const CHANNEL_COLORS: Record<string, string> = {
  organic_search: "#0053CD", organic: "#0053CD",
  paid_search:    "#A855F7", paid:    "#A855F7",
  direct_traffic: "#10B981", direct:  "#10B981",
  referral:       "#F59E0B",
  social:         "#E11D48",
  email:          "#06B6D4",
  affiliate:      "#8B5CF6",
};

interface ChannelRow {
  channel: string;
  rank: number;
  customers: number;
  orders: number;
  revenue: number;
  aov: number;
  avg_ltv: number;
  rev_share_pct: number;
  cust_share_pct: number;
}

interface A14Data {
  question?: string;
  headline?: {
    value?: number; label?: string;
    trend_pct?: number | null;
    trend_direction?: "up" | "down" | "flat" | null;
    period?: string;
  };
  summary?: {
    n_customers?: number; n_channels?: number;
    total_revenue?: number;
    best_channel_revenue?: { name: string; revenue: number; share_pct: number } | null;
    best_channel_aov?:     { name: string; aov: number } | null;
    best_channel_ltv?:     { name: string; avg_ltv: number } | null;
    channel_concentration?: number;
  };
  by_channel?: ChannelRow[];
  fallback_bullets?: string[];
  suggested_actions?: SuggestedAction[];
}

interface Props { data: A14Data; moduleKey: string; }

function channelColor(name: string, fallbackIdx: number): string {
  const key = name.toLowerCase().replace(/[\s-]+/g, "_");
  return CHANNEL_COLORS[key] || paletteColor(fallbackIdx);
}

export function A14ChannelChart({ data, moduleKey }: Props) {
  const t = useChartTheme();

  const rows = data?.by_channel || [];
  const ranked = useMemo(
    () => [...rows].sort((a, b) => b.revenue - a.revenue).slice(0, 5),
    [rows],
  );
  const headline = data?.headline ?? {};
  const summary = data?.summary ?? {};
  const bestAov = summary?.best_channel_aov;
  const bestLtv = summary?.best_channel_ltv;

  const question = data?.question || "Which marketing channel is bringing me the most customers?";

  return (
    <DecisionCardShell
      moduleKey={moduleKey.replace("_acquisition_channel", "").toUpperCase()}
      question={question}
      period={headline.period || "Last 30 days"}
      headlineValue={typeof headline.value === "number" ? fmtCompact(headline.value, 0) : "—"}
      headlineLabel={headline.label || "new customers"}
      trendPct={headline.trend_pct ?? null}
      trendPeriod={headline.trend_pct != null ? "vs last month" : undefined}
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
            // Visual-only deeplink today — full nav wired post-defense.
            // eslint-disable-next-line no-console
            console.log("A14 action click:", a);
          }}
        />
      }
    >
      {ranked.length === 0 ? (
        <div
          className="w-full h-full min-h-[180px] flex items-center justify-center text-[12px]"
          style={{ color: t.text.muted }}
        >
          No acquisition_channel data yet.
        </div>
      ) : (
        <div className="w-full h-full flex flex-col gap-3 pt-1">
          {/* Ranked channel bars ─ the visual core */}
          <ul className="space-y-1.5">
            {ranked.map((r, idx) => {
              const color = channelColor(r.channel, idx);
              const widthPct = Math.max(2, Math.min(100, r.rev_share_pct));
              const isTop = idx === 0;
              return (
                <li
                  key={r.channel}
                  className="rounded-md px-2 py-1.5 transition-colors"
                  style={{
                    background: isTop ? t.semanticSoft.brand : "transparent",
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className="text-[10px] font-bold w-4 text-center"
                      style={{ color: t.text.faint }}
                    >
                      {r.rank}
                    </span>
                    <span
                      className="text-[12px] font-semibold capitalize flex-1 truncate"
                      style={{ color: isTop ? t.semantic.brand : t.text.headline }}
                    >
                      {r.channel.replace(/_/g, " ")}
                    </span>
                    <span
                      className="text-[11px] font-bold tabular-nums shrink-0"
                      style={{ color: t.text.headline }}
                    >
                      {fmtCompact(r.customers, 0)}
                      <span className="font-normal" style={{ color: t.text.faint }}>
                        {" "}cust
                      </span>
                    </span>
                    <span
                      className="text-[10px] font-bold tabular-nums shrink-0 w-9 text-right"
                      style={{ color: isTop ? t.semantic.brand : t.text.muted }}
                    >
                      {r.rev_share_pct.toFixed(0)}%
                    </span>
                  </div>
                  {/* Bar */}
                  <div
                    className="w-full h-1.5 rounded-full overflow-hidden"
                    style={{ background: t.surfaceMuted }}
                  >
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${widthPct}%`,
                        background: color,
                        boxShadow: isTop ? `0 0 8px ${color}55` : "none",
                      }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>

          {/* Quality strip — AOV winner + LTV winner */}
          {(bestAov || bestLtv) && (
            <div
              className="grid grid-cols-2 gap-2 mt-auto pt-2 border-t"
              style={{ borderColor: t.border }}
            >
              {bestAov && (
                <div
                  className="rounded-md p-2 border"
                  style={{ background: t.surfaceMuted, borderColor: t.border }}
                >
                  <p
                    className="text-[9px] font-bold uppercase tracking-wider"
                    style={{ color: t.text.faint }}
                  >
                    Highest AOV
                  </p>
                  <p
                    className="text-[11.5px] font-semibold capitalize mt-0.5 truncate"
                    style={{ color: t.text.headline }}
                  >
                    {String(bestAov.name).replace(/_/g, " ")}
                  </p>
                  <p
                    className="text-[10px] tabular-nums"
                    style={{ color: t.semantic.positive }}
                  >
                    ${fmtCompact(bestAov.aov, 0)} / order
                  </p>
                </div>
              )}
              {bestLtv && (
                <div
                  className="rounded-md p-2 border"
                  style={{ background: t.surfaceMuted, borderColor: t.border }}
                >
                  <p
                    className="text-[9px] font-bold uppercase tracking-wider"
                    style={{ color: t.text.faint }}
                  >
                    Highest LTV
                  </p>
                  <p
                    className="text-[11.5px] font-semibold capitalize mt-0.5 truncate"
                    style={{ color: t.text.headline }}
                  >
                    {String(bestLtv.name).replace(/_/g, " ")}
                  </p>
                  <p
                    className="text-[10px] tabular-nums"
                    style={{ color: t.semantic.positive }}
                  >
                    ${fmtCompact(bestLtv.avg_ltv, 0)} / cust
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </DecisionCardShell>
  );
}
