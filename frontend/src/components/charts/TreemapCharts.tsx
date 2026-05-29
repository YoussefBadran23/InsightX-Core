"use client";

/**
 * Treemap charts for hierarchical / share-of-pie visualisations.
 *
 * Note: A14 Acquisition Channel was promoted out of this file into the new
 * Decision-Chart shell — see `A14ChannelChart.tsx`. It is the gold-standard
 * reference every other chart copies for the v1 redesign.
 */

import { ResponsiveContainer, Treemap, Tooltip } from "recharts";
import { InsightCard } from "./foundation/InsightCard";
import { InsightTooltip } from "./foundation/InsightTooltip";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";
import { fmtCompact, paletteColor, NoDataState } from "./chartHelpers";

interface TreeRow { name: string; size: number; color: string; }

function TreemapChart({ rows }: { rows: TreeRow[] }) {
  if (rows.length === 0) return <NoDataState />;
  return (
    <div className="w-full h-full relative">
      <ResponsiveContainer width="100%" height="100%">
        <Treemap
          data={rows as any}
          dataKey="size"
          // @ts-expect-error — Recharts' Treemap content prop typing is loose
          content={(props: any) => {
            const { x, y, width, height, color, name } = props;
            if (width < 30 || height < 20) {
              return (
                <rect x={x} y={y} width={width} height={height} fill={color}
                  stroke="var(--surface-card, #ffffff)" strokeWidth={2} rx={4} ry={4} />
              );
            }
            return (
              <g>
                <rect x={x} y={y} width={width} height={height} fill={color}
                  stroke="var(--surface-card, #ffffff)" strokeWidth={2} rx={6} ry={6}
                  className="transition-all hover:opacity-90" />
                <text x={x + 8} y={y + 18} fontSize={12} fill="#ffffff" fontWeight={600}
                  className="pointer-events-none">
                  {(name || "").slice(0, Math.floor(width / 8))}
                </text>
              </g>
            );
          }}
        >
          <Tooltip
            content={<InsightTooltip />}
            cursor={{ fill: "rgba(255,255,255,0.05)" }}
            formatter={(v: any) => [fmtCompact(Number(v)), "Revenue"]}
          />
        </Treemap>
      </ResponsiveContainer>
    </div>
  );
}

/* ── P02 Category Performance · Decision-Chart v1 ───────────────────────
   Question: "Which category of products is making me the most money?" */
export function P02CategoryChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const list = data?.by_category || data?.categories || [];
  const rows: TreeRow[] = list.map((c: any, i: number) => ({
    name: c.category || c.name,
    size: Number(c.revenue || c.total || 0),
    color: paletteColor(i),
  }));
  const headline = data?.headline ?? {};
  const question = data?.question || "Which category of products is making me the most money?";
  const topCat = list.length ? list.reduce((a: any, b: any) => (Number(a.revenue || 0) > Number(b.revenue || 0) ? a : b)) : null;
  const topName = topCat ? String(topCat.category || topCat.name || "—") : "—";

  return (
    <DecisionCardShell
      moduleKey="P02"
      question={question}
      period={headline.period || `${list.length} categories`}
      headlineValue={topName.slice(0, 22)}
      headlineLabel={
        topCat
          ? `top category · ${fmtCompact(Number(topCat.revenue || 0), 0)}`
          : "no categories yet"
      }
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[200px] p-1">
        <TreemapChart rows={rows} />
      </div>
    </DecisionCardShell>
  );
}
