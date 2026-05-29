"use client";

/**
 * Horizontal bar charts for top-N rankings:
 *   A09 Top N Products, A24 Basket Recommendations,
 *   C02 Top Customers, P01 Product Ranking.
 *
 * All four share the same shape ("rank items by some value") so they share
 * a generic <RankBar> primitive — each chart only writes the data adapter.
 */

import { useState } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from "recharts";
import { InsightCard } from "./foundation/InsightCard";
import { InsightTooltip } from "./foundation/InsightTooltip";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";
import { useAuthStore } from "@/stores/authStore";
import { useJobStore } from "@/stores/jobStore";
import { formatMoney } from "@/lib/format";
import { truncate, paletteColor, NoDataState, useChartTheme, fmtCompact } from "./chartHelpers";

interface RankRow { label: string; value: number; sublabel?: string; }
interface RankBarProps {
  rows: RankRow[];
  /** Widened to match InsightTooltip's `valueFormatter` signature — Recharts
   *  payload values can be string or number depending on the series. */
  valueFormatter?: (v: number | string) => string;
  emptyMsg?: string;
  currency?: string;
  sourceCurrency?: string;
}

function RankBar({ rows, valueFormatter, emptyMsg, currency = "USD", sourceCurrency = "USD" }: RankBarProps) {
  const theme = useChartTheme();
  if (rows.length === 0) return <NoDataState message={emptyMsg} />;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows.slice(0, 12)} layout="vertical" margin={{ top: 4, right: 30, left: 8, bottom: 4 }}>
        <XAxis type="number" hide />
        <YAxis
          dataKey="label"
          type="category"
          width={120}
          tick={{ fontSize: 11, fill: '#888' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: string) => truncate(v, 18)}
        />
        <Tooltip content={<InsightTooltip currency={currency} sourceCurrency={sourceCurrency} valueFormatter={valueFormatter} />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {rows.slice(0, 12).map((_, i) => (
            <Cell key={i} fill={paletteColor(i)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── A09 Top N Products · Decision-Chart v1 ──────────────────────────────
   Question: "What's my best-selling product this week?"                     */
export function A09TopProductsChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const allProducts: any[] = data?.top_by_revenue || data?.top_products || data?.products || [];
  const [topN, setTopN] = useState<5 | 10 | 25>(10);
  const theme = useChartTheme();

  const user = useAuthStore((s) => s.user);
  const currency = user?.preferred_currency || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);

  const products = allProducts.slice(0, topN);
  const maxRev = Math.max(...products.map((p: any) => Number(p.revenue) || 0), 1);
  const minRev = Math.min(...products.map((p: any) => Number(p.revenue) || 0), Infinity);

  const headline = data?.headline ?? {};
  const question = data?.question || "What's my best-selling product this week?";
  const topProduct = allProducts[0];

  // Top N selector renders inside the shell's headerRight slot
  const headerRight = allProducts.length > 0 ? (
    <div
      className="flex items-center gap-0.5 rounded-md p-0.5"
      style={{ background: theme.surfaceMuted, border: `1px solid ${theme.border}` }}
    >
      {([5, 10, 25] as const).map((n) => (
        <button
          key={n}
          onClick={() => setTopN(n)}
          className="px-2 py-1 text-[10px] font-semibold rounded transition-colors"
          style={{
            background: topN === n ? theme.semantic.brand : "transparent",
            color: topN === n ? "#fff" : theme.text.muted,
          }}
        >
          Top {n}
        </button>
      ))}
    </div>
  ) : null;

  return (
    <DecisionCardShell
      moduleKey="A09"
      question={question}
      period={headline.period || "All time"}
      headlineValue={
        topProduct
          ? truncate(topProduct.product_name || topProduct.name || topProduct.product_id || "—", 24)
          : "—"
      }
      headlineLabel={
        topProduct
          ? `best seller · ${formatMoney(Number(topProduct.revenue) || 0, currency, { from: sourceCurrency })}`
          : "best seller"
      }
      trendPct={null}
      headerRight={headerRight}
      aiInsight={
        <AIInsightPanel moduleKey={moduleKey} question={question} data={data} />
      }
      actions={
        <ActionChipRow
          actions={(data?.suggested_actions as SuggestedAction[]) || []}
          onAction={(a) => { /* visual deeplink */ void a; }}
        />
      }
    >
      {allProducts.length === 0 ? (
        <NoDataState />
      ) : (
        <div className="flex-1 min-h-0 overflow-auto pr-1 custom-scrollbar">
          <table className="w-full text-left">
            <thead
              className="text-[10px] uppercase tracking-wider sticky top-0 backdrop-blur-sm z-10"
              style={{
                color: theme.text.muted,
                background: `${theme.surface}E6`,
              }}
            >
              <tr style={{ borderBottom: `1px solid ${theme.border}` }}>
                <th className="px-2 py-2 w-10">#</th>
                <th className="px-2 py-2">Product</th>
                <th className="px-2 py-2 text-right w-20">Volume</th>
                <th className="px-2 py-2 text-right w-24">Revenue</th>
                <th className="px-2 py-2 pl-4 w-1/3">Share of Top</th>
              </tr>
            </thead>
            <tbody className="text-[12px]">
              {products.map((p: any, i: number) => {
                const rev = Number(p.revenue) || 0;
                const volume = Number(p.units ?? p.quantity ?? p.orders ?? 0);
                const pct = maxRev > 0 ? (rev / maxRev) * 100 : 0;
                const isLowest = rev === minRev && rev < maxRev * 0.25;
                const isTop = i === 0;
                const nameStr = p.product_name || p.name || p.product_id || `Product #${i + 1}`;
                return (
                  <tr
                    key={p.product_id || p.id || i}
                    className="transition-colors"
                    style={{
                      borderBottom: `1px solid ${theme.border}`,
                    }}
                  >
                    <td
                      className="px-2 py-2 font-bold"
                      style={{ color: isTop ? theme.semantic.brand : theme.text.faint }}
                    >
                      {i + 1}
                    </td>
                    <td
                      className="px-2 py-2 font-semibold truncate max-w-[180px]"
                      title={nameStr}
                      style={{ color: theme.text.headline }}
                    >
                      {truncate(nameStr, 32)}
                    </td>
                    <td
                      className="px-2 py-2 text-right tabular-nums"
                      style={{ color: theme.text.muted }}
                    >
                      {volume > 0 ? fmtCompact(volume, 0) : "—"}
                    </td>
                    <td
                      className="px-2 py-2 text-right font-bold tabular-nums"
                      style={{
                        color: isTop
                          ? theme.semantic.positive
                          : isLowest
                            ? theme.semantic.warning
                            : theme.text.headline,
                      }}
                    >
                      {formatMoney(rev, currency, { from: sourceCurrency })}
                    </td>
                    <td className="px-2 py-2 pl-4">
                      <div
                        className="w-full rounded-full h-1.5 overflow-hidden"
                        style={{ background: theme.surfaceMuted }}
                      >
                        <div
                          className="h-full rounded-full transition-all duration-700 ease-out"
                          style={{
                            width: `${Math.max(2, pct)}%`,
                            background: isTop
                              ? `linear-gradient(to right, ${theme.semantic.brand}, ${theme.semantic.brand}cc)`
                              : theme.semantic.brand + "AA",
                            boxShadow: isTop ? `0 0 8px ${theme.semantic.brand}66` : "none",
                          }}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </DecisionCardShell>
  );
}

/* ── A24 Basket Recommendations · Decision-Chart v1 ─────────────────────
   Question: "What should I cross-sell with each product?"               */
export function A24BasketRecsChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const recs = data?.recommendations || data?.top_recommendations || data?.top_pairs || [];
  const rows = recs.map((r: any) => ({
    label: `${r.antecedent_name || r.antecedent} → ${r.consequent_name || r.consequent}`,
    value: Number(r.lift ?? r.score ?? 0),
  }));
  const headline = data?.headline ?? {};
  const question = data?.question || "What should I cross-sell with each product?";
  const topPair = recs[0];
  const topLift = topPair ? Number(topPair.lift ?? topPair.score ?? 0) : 0;

  return (
    <DecisionCardShell
      moduleKey="A24"
      question={question}
      period={headline.period || "All orders"}
      headlineValue={topPair ? `${topLift.toFixed(2)}×` : "—"}
      headlineLabel={headline.label || "strongest pair lift"}
      headlineKind={topLift >= 2 ? "positive" : "neutral"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[200px]">
        <RankBar rows={rows} valueFormatter={(v) => `${Number(v).toFixed(2)}×`} emptyMsg="No basket recommendations" />
      </div>
    </DecisionCardShell>
  );
}

/* ── C02 Top Customers · Decision-Chart v1 ──────────────────────────────
   Question: "Who are my top 10 customers by total spend?"               */
export function C02TopCustomersChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const user = useAuthStore((s) => s.user);
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const currency = user?.preferred_currency || 'USD';

  const customers = data?.top_customers || data?.customers || [];
  const rows = customers.map((c: any) => ({
    label: c.customer_name || c.name || c.customer_id || "Unknown Customer",
    value: Number(c.lifetime_value ?? c.revenue ?? c.total ?? 0),
  }));
  const headline = data?.headline ?? {};
  const question = data?.question || "Who are my top customers by total spend?";
  const top1 = customers[0];
  const top1Name = top1?.name || top1?.customer_name || top1?.email || top1?.customer_id || "—";

  return (
    <DecisionCardShell
      moduleKey="C02"
      question={question}
      period={headline.period || "All time"}
      headlineValue={String(top1Name).slice(0, 28)}
      headlineLabel={
        top1
          ? `#1 customer · ${formatMoney(Number(top1?.lifetime_value ?? top1?.revenue ?? 0), currency, { from: sourceCurrency })}`
          : "no customers yet"
      }
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[200px]">
        <RankBar rows={rows} currency={currency} sourceCurrency={sourceCurrency} />
      </div>
    </DecisionCardShell>
  );
}

/* ── P01 Product Revenue Ranking · Decision-Chart v1 ────────────────────
   Question: "Which products are pulling their weight?"                  */
export function P01ProductRankingChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const user = useAuthStore((s) => s.user);
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const currency = user?.preferred_currency || 'USD';

  const list = data?.ranking || data?.products || data?.top_products || data?.top_by_revenue || [];
  const rows = list.map((p: any) => ({
    label: p.product_name || p.name || p.product_id || "Unknown Product",
    value: Number(p.revenue ?? p.total ?? 0),
  }));
  const headline = data?.headline ?? {};
  const question = data?.question || "Which products are pulling their weight?";
  const topProduct = list[0];
  const topRevShare = Number(headline.value ?? 0);

  return (
    <DecisionCardShell
      moduleKey="P01"
      question={question}
      period={headline.period || "All time"}
      headlineValue={topRevShare > 0 ? `${topRevShare.toFixed(1)}%` : (topProduct ? truncate(topProduct.name || topProduct.product_id, 24) : "—")}
      headlineLabel={topRevShare > 0 ? (headline.label || "revenue from top 10") : "best seller"}
      headlineKind={topRevShare >= 70 ? "warning" : "positive"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-[200px]">
        <RankBar rows={rows} currency={currency} sourceCurrency={sourceCurrency} />
      </div>
    </DecisionCardShell>
  );
}
