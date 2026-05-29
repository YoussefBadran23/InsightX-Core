"use client";

/**
 * Stacked-bar charts for composition-over-time / categorical splits:
 *   A04 Gross Margin (revenue vs cost),
 *   A12 Discount Impact (discounted vs full-price share by month),
 *   A18 Sentiment Analysis (pos/neu/neg distribution),
 *   C04 New vs Returning customers (per month).
 */

import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ComposedChart, Line, ReferenceLine } from "recharts";
import { InsightCard } from "./foundation/InsightCard";
import { InsightTooltip } from "./foundation/InsightTooltip";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";
import { fmtCompact, NoDataState, useChartTheme } from "./chartHelpers";
import { useAuthStore } from "@/stores/authStore";
import { useJobStore } from "@/stores/jobStore";
import { formatMoney } from "@/lib/format";

/* ── A04 Gross Margin · Decision-Chart v1 ───────────────────────────────
   Question: "Am I making real money, or just moving inventory?"      */
export function A04GrossMarginChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const theme = useChartTheme();
  const user = useAuthStore((s) => s.user);
  const currency = user?.preferred_currency || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const headline = data?.headline ?? {};
  const question = data?.question || "Am I making real money, or just moving inventory?";

  const monthly: any[] = data?.by_period?.monthly || data?.monthly || [];
  if (monthly.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A04"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="gross margin"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState />
      </DecisionCardShell>
    );
  }

  const rows = monthly.map((m: any) => {
    const revenue = Number(m.revenue ?? m.gross ?? 0);
    const cost    = Number(m.cost ?? 0);
    const profit  = Number(m.margin ?? Math.max(0, revenue - cost));
    const marginPct = m.margin_pct != null ? Number(m.margin_pct) : revenue > 0 ? (profit / revenue) * 100 : 0;
    return {
      period: String(m.period || m.label || ""),
      profit: Math.max(0, profit),
      marginPct: Number(marginPct.toFixed(1)),
    };
  });

  const target = Number(data?.target_margin_pct ?? 60);
  const last = rows[rows.length - 1];
  const aboveTarget = last && last.marginPct >= target;
  const firstM = rows[0]?.marginPct ?? 0;
  const lastM = last?.marginPct ?? 0;
  const yoy = lastM - firstM;

  // ── Direct-answer composition: Revenue = Cost + Margin ────────────────
  // Sums across the visible window so the bar shows "how much of revenue
  // became actual profit". Bigger green segment = "yes I'm making money".
  const sumRev = rows.reduce((acc, r) => acc + (r.profit > 0 ? r.profit / Math.max(r.marginPct / 100, 0.01) : 0), 0);
  const sumProfit = rows.reduce((acc, r) => acc + r.profit, 0);
  const sumCost = Math.max(0, sumRev - sumProfit);
  const profitPct = sumRev > 0 ? (sumProfit / sumRev) * 100 : 0;
  const costPct = sumRev > 0 ? (sumCost / sumRev) * 100 : 0;

  return (
    <DecisionCardShell
      moduleKey="A04"
      question={question}
      period={headline.period || "Monthly trend"}
      headlineValue={`${(Number(headline.value ?? lastM)).toFixed(1)}%`}
      headlineLabel={headline.label || `latest gross margin · target ${target}%`}
      trendPct={headline.trend_pct ?? yoy}
      trendPeriod="vs first period"
      headlineKind={aboveTarget ? "positive" : lastM > 0 ? "warning" : "danger"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      {/* ── Revenue / Cost / Margin composition · the direct visual answer ──
          One bar showing the share of revenue that became profit. Green = kept,
          red = swallowed by cost. The eye reads "yes I made money" or "no
          I'm just churning revenue" in under a second. */}
      {sumRev > 0 && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider mb-1">
            <span style={{ color: theme.semantic.positive }}>
              Margin · {fmtCompact(sumProfit, 0)} kept
            </span>
            <span style={{ color: theme.semantic.danger }}>
              Cost · {fmtCompact(sumCost, 0)} spent
            </span>
          </div>
          <div
            className="w-full h-7 rounded-md overflow-hidden flex"
            style={{
              background: theme.surfaceMuted,
              border: `1px solid ${theme.border}`,
            }}
          >
            {profitPct > 0 && (
              <div
                className="h-full transition-all flex items-center justify-center text-[10px] font-extrabold text-white"
                style={{
                  width: `${Math.max(profitPct, 4)}%`,
                  background: theme.semantic.positive,
                  boxShadow: `inset 0 0 14px ${theme.semantic.positive}99`,
                }}
                title={`${profitPct.toFixed(1)}% of revenue kept as profit`}
              >
                {profitPct >= 12 ? `${profitPct.toFixed(0)}%` : ""}
              </div>
            )}
            {costPct > 0 && (
              <div
                className="h-full transition-all flex items-center justify-center text-[10px] font-extrabold text-white"
                style={{
                  width: `${Math.max(costPct, 4)}%`,
                  background: theme.semantic.danger,
                  boxShadow: `inset 0 0 14px ${theme.semantic.danger}99`,
                }}
                title={`${costPct.toFixed(1)}% swallowed by cost`}
              >
                {costPct >= 12 ? `${costPct.toFixed(0)}%` : ""}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-4 mb-2">
        <span className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300 font-medium">
          <span className="w-3 h-0.5 bg-primary" /> Actual Margin
        </span>
        <span className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300 font-medium">
          <span className="w-3 border-t-2 border-dashed border-slate-400" /> Target
        </span>
        <span className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300 font-medium">
          <span className="w-2.5 h-2.5 rounded-sm bg-slate-200 dark:bg-slate-600" /> Gross Profit
        </span>
      </div>

      <div className="flex-1 min-h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 0, left: -20, bottom: 0 }}>
            <defs>
              <filter id="a04-line-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="2.5" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={theme.gridStroke} opacity={0.4} />
            <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} minTickGap={16} />
            <YAxis yAxisId="pct" orientation="left" domain={[40, 80]} ticks={[40, 50, 60, 70, 80]} tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} width={40} />
            <YAxis yAxisId="$" orientation="right" tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} tickFormatter={(v) => formatMoney(v, currency, { from: sourceCurrency, compact: true })} width={50} />
            
            <Tooltip content={<InsightTooltip currency={currency} sourceCurrency={sourceCurrency} />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />

            <Bar yAxisId="$" dataKey="profit" name="Gross Profit" fill="var(--slate-200, #e2e8f0)" radius={[4, 4, 0, 0]} maxBarSize={36} />
            
            <ReferenceLine yAxisId="pct" y={target} stroke="#94a3b8" strokeDasharray="6 4" strokeWidth={2} label={{ value: `Target ${target}%`, position: "insideTopRight", fill: "#94a3b8", fontSize: 10 }} />
            
            <Line yAxisId="pct" type="monotone" dataKey="marginPct" name="Margin %" stroke={theme.primary} strokeWidth={3} dot={{ r: 4, fill: theme.cardBg, stroke: theme.primary, strokeWidth: 2 }} activeDot={{ r: 6, fill: theme.primary, stroke: theme.cardBg, strokeWidth: 2 }} filter="url(#a04-line-glow)" isAnimationActive={true} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </DecisionCardShell>
  );
}

/* ── A12 Discount Impact · Decision-Chart v1 ─────────────────────────────
   Question: "Did my last promotion actually make me money?"             */
export function A12DiscountChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const theme = useChartTheme();
  const user = useAuthStore((s) => s.user);
  const currency = user?.preferred_currency || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);

  const bands: any[] = data?.by_discount_band || data?.discount_bands || [];
  const summary = data?.summary || {};
  const headline = data?.headline ?? {};
  const question = data?.question || "Did my last promotion actually make me money?";
  const totalDiscount = Number(summary.total_discount ?? headline.value ?? 0);
  const discountSharePct = Number(summary.discount_pct_of_gross ?? 0);

  if (bands.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A12"
        question={question}
        period="no data"
        headlineValue={formatMoney(totalDiscount, currency, { from: sourceCurrency })}
        headlineLabel="given in discounts"
        trendPct={null}
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState message="Discount-band aggregation not available." />
      </DecisionCardShell>
    );
  }

  const rows = bands.map((b: any) => ({
    rate: Number(b.rate_pct ?? b.discount_pct ?? b.rate ?? 0),
    revenue: Number(b.revenue ?? b.total ?? 0),
    volume: Number(b.volume ?? b.orders ?? b.order_count ?? 0),
  }));

  // ── Side-by-side comparison · the visual answer ──────────────────────
  // The worker hands us a `comparison` block with both halves (discounted vs
  // full-price). If the worker is older or the field is missing we synthesise
  // it from the bands so the visual still renders something useful.
  const comparison = (data?.comparison as any) || (() => {
    const disc = rows.filter((r) => r.rate > 0);
    const full = rows.filter((r) => r.rate === 0);
    const discRev = disc.reduce((acc, r) => acc + r.revenue, 0);
    const fullRev = full.reduce((acc, r) => acc + r.revenue, 0);
    const discOrders = disc.reduce((acc, r) => acc + r.volume, 0);
    const fullOrders = full.reduce((acc, r) => acc + r.volume, 0);
    return {
      discounted: {
        orders: discOrders,
        revenue: discRev,
        aov: discOrders > 0 ? discRev / discOrders : 0,
        discount: totalDiscount,
      },
      full_price: {
        orders: fullOrders,
        revenue: fullRev,
        aov: fullOrders > 0 ? fullRev / fullOrders : 0,
      },
      aov_ratio: 0,
    };
  })();

  const disc = comparison?.discounted || {};
  const full = comparison?.full_price || {};
  const aovRatio = Number(comparison?.aov_ratio ?? (full.aov > 0 ? disc.aov / full.aov : 0));

  // Verdict pill — does the discounted basket actually beat the full-price one?
  const verdict =
    aovRatio >= 1.10
      ? { kind: "positive" as const, label: `Promo grew basket by +${((aovRatio - 1) * 100).toFixed(0)}%`, color: theme.semantic.positive, bg: theme.semanticSoft.positive }
      : aovRatio <= 0.85 && aovRatio > 0
      ? { kind: "danger" as const, label: `Promo shrunk basket by ${((1 - aovRatio) * 100).toFixed(0)}%`, color: theme.semantic.danger, bg: theme.semanticSoft.danger }
      : aovRatio > 0
      ? { kind: "neutral" as const, label: `Neutral · ${aovRatio.toFixed(2)}× basket vs full-price`, color: theme.text.muted, bg: theme.surfaceMuted }
      : null;

  return (
    <DecisionCardShell
      moduleKey="A12"
      question={question}
      period={headline.period || "All time"}
      headlineValue={formatMoney(totalDiscount, currency, { from: sourceCurrency })}
      headlineLabel={headline.label || `given in discounts · ${discountSharePct.toFixed(1)}% of gross`}
      trendPct={null}
      headlineKind={verdict?.kind || "neutral"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="w-full h-full flex flex-col gap-2.5 pt-1">
        {/* ── Two-card head-to-head ─────────────────────────────────────
            LEFT = orders the customer paid full price for.
            RIGHT = orders sold with a discount.
            Each card shows revenue (the big number), orders count, and AOV.
            Reading both at once tells you whether discounting changed
            customer behaviour, not just the revenue pile. */}
        <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
          {/* Without discount */}
          <div
            className="rounded-lg p-3 flex flex-col"
            style={{
              background: theme.surfaceMuted,
              border: `1px solid ${theme.border}`,
            }}
          >
            <p
              className="text-[9.5px] font-bold uppercase tracking-wider"
              style={{ color: theme.text.faint }}
            >
              Without discount
            </p>
            <p
              className="text-[18px] font-extrabold tabular-nums leading-none mt-1.5"
              style={{ color: theme.text.headline }}
            >
              {formatMoney(Number(full.revenue ?? 0), currency, { from: sourceCurrency, compact: true })}
            </p>
            <p
              className="text-[10px] mt-1"
              style={{ color: theme.text.muted }}
            >
              {fmtCompact(Number(full.orders ?? 0), 0)} orders
            </p>
            <div
              className="mt-auto pt-2 border-t"
              style={{ borderColor: theme.border }}
            >
              <p
                className="text-[9.5px] font-bold uppercase tracking-wider"
                style={{ color: theme.text.faint }}
              >
                AOV
              </p>
              <p
                className="text-[13px] font-bold tabular-nums"
                style={{ color: theme.text.body }}
              >
                {formatMoney(Number(full.aov ?? 0), currency, { from: sourceCurrency })}
              </p>
            </div>
          </div>

          {/* With discount */}
          <div
            className="rounded-lg p-3 flex flex-col relative overflow-hidden"
            style={{
              background: theme.semanticSoft.brand,
              border: `1px solid ${theme.semantic.brand}44`,
              boxShadow: `0 0 0 1px ${theme.semantic.brand}1a`,
            }}
          >
            <p
              className="text-[9.5px] font-bold uppercase tracking-wider"
              style={{ color: theme.semantic.brand }}
            >
              With discount
            </p>
            <p
              className="text-[18px] font-extrabold tabular-nums leading-none mt-1.5"
              style={{ color: theme.text.headline }}
            >
              {formatMoney(Number(disc.revenue ?? 0), currency, { from: sourceCurrency, compact: true })}
            </p>
            <p
              className="text-[10px] mt-1"
              style={{ color: theme.text.muted }}
            >
              {fmtCompact(Number(disc.orders ?? 0), 0)} orders · −{formatMoney(Number(disc.discount ?? totalDiscount), currency, { from: sourceCurrency, compact: true })} given
            </p>
            <div
              className="mt-auto pt-2 border-t"
              style={{ borderColor: theme.border }}
            >
              <p
                className="text-[9.5px] font-bold uppercase tracking-wider"
                style={{ color: theme.semantic.brand }}
              >
                AOV
              </p>
              <p
                className="text-[13px] font-bold tabular-nums"
                style={{ color: theme.text.body }}
              >
                {formatMoney(Number(disc.aov ?? 0), currency, { from: sourceCurrency })}
              </p>
            </div>
          </div>
        </div>

        {/* Verdict pill — the one-line read of whether the promo paid off. */}
        {verdict && (
          <div
            className="rounded-md px-3 py-1.5 text-center flex items-center justify-center gap-2"
            style={{
              background: verdict.bg,
              border: `1px solid ${verdict.color}44`,
            }}
          >
            <span
              className="text-[11px] font-bold uppercase tracking-wider"
              style={{ color: verdict.color }}
            >
              {verdict.label}
            </span>
          </div>
        )}
      </div>
    </DecisionCardShell>
  );
}

/* ── A18 Sentiment Distribution · Decision-Chart v1 ──────────────────────
   Question: "Are my customers happy or upset about something?"          */
export function A18SentimentChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const byCat = data?.by_category || [];
  let rows = [];

  if (byCat.length === 0) {
    const s = data?.summary || {};
    rows = [
      { period: "Overall", positive: Number(s.positive_pct || 0), neutral: Number(s.neutral_pct || 0), negative: Number(s.negative_pct || 0) },
    ];
  } else {
    rows = byCat.slice(0, 10).map((c: any) => ({
      period: c.category,
      positive: Number(c.positive_pct || 0),
      neutral: 100 - Number(c.positive_pct || 0) - Number(c.negative_pct || 0),
      negative: Number(c.negative_pct || 0),
    }));
  }

  const theme = useChartTheme();
  const headline = data?.headline ?? {};
  const question = data?.question || "Are my customers happy or upset about something?";
  const s = data?.summary || {};
  const posPct = Number(headline.value ?? s.positive_pct ?? 0);
  const negPct = Number(s.negative_pct ?? 0);

  return (
    <DecisionCardShell
      moduleKey="A18"
      question={question}
      period={headline.period || "All comments"}
      headlineValue={`${posPct.toFixed(1)}%`}
      headlineLabel={headline.label || "positive sentiment"}
      trendPct={null}
      headlineKind={posPct >= 70 ? "positive" : negPct >= 30 ? "danger" : "warning"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex flex-wrap gap-3 mb-2">
        <span className="flex items-center gap-1.5 text-[11px] font-medium" style={{ color: theme.text.body }}>
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: theme.semantic.positive }} /> Positive
        </span>
        <span className="flex items-center gap-1.5 text-[11px] font-medium" style={{ color: theme.text.body }}>
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: theme.text.faint }} /> Neutral
        </span>
        <span className="flex items-center gap-1.5 text-[11px] font-medium" style={{ color: theme.text.body }}>
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: theme.semantic.danger }} /> Negative
        </span>
      </div>

      <div className="flex-1 min-h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={theme.gridStroke} opacity={0.5} />
            <XAxis type="number" tick={{ fontSize: 10, fill: theme.text.muted }} tickLine={false} axisLine={false} unit="%" />
            <YAxis dataKey="period" type="category" width={100} tick={{ fontSize: 10, fill: theme.text.muted }} tickLine={false} axisLine={false} />
            <Tooltip content={<InsightTooltip valueFormatter={(v) => `${Number(v).toFixed(1)}%`} />} cursor={{ fill: 'rgba(148,163,184,0.08)' }} />
            <Bar dataKey="positive" stackId="a" fill={theme.semantic.positive} name="Positive" />
            <Bar dataKey="neutral" stackId="a" fill={theme.text.faint} name="Neutral" />
            <Bar dataKey="negative" stackId="a" fill={theme.semantic.danger} name="Negative" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </DecisionCardShell>
  );
}

/* ── C04 Customer Composition · Decision-Chart v1 ───────────────────────
   Question: "How many of today's orders came from people who already bought before?" */
export function C04NewVsReturningChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const c04Theme = useChartTheme();
  const monthly = data?.monthly_trend || data?.monthly || data?.by_period || [];
  const headline = data?.headline ?? {};
  const question = data?.question || "How many of today's orders came from people who already bought before?";
  if (monthly.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="C04"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="orders from returning customers"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState />
      </DecisionCardShell>
    );
  }

  const rows = monthly.map((m: any) => ({
    period: m.period || m.month,
    new: Number(m.new_orders ?? m.new_customers ?? m.new ?? 0),
    returning: Number(m.returning_orders ?? m.returning_customers ?? m.returning ?? 0),
  }));
  const summary = data?.summary || {};
  const returningPct = Number(headline.value ?? summary.returning_orders_pct ?? 0);
  const newPct = Math.max(0, 100 - returningPct);
  const nReturningOrders = Number(summary.n_returning_customer_orders ?? 0);
  const nNewOrders = Number(summary.n_new_customer_orders ?? 0);

  return (
    <DecisionCardShell
      moduleKey="C04"
      question={question}
      period={headline.period || "Monthly trend"}
      headlineValue={`${returningPct.toFixed(1)}%`}
      headlineLabel={headline.label || "orders from returning customers"}
      headlineKind={returningPct >= 50 ? "positive" : returningPct >= 25 ? "neutral" : "warning"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      {/* ── Direct-answer overall split bar ────────────────────────────
          One horizontal bar showing returning vs new across the whole
          window. Big green portion = healthy repeat business; big blue
          portion = stuck on the acquisition treadmill. */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider mb-1">
          <span style={{ color: c04Theme.semantic.positive }}>
            Returning · {fmtCompact(nReturningOrders, 0)} orders
          </span>
          <span style={{ color: c04Theme.semantic.brand }}>
            New · {fmtCompact(nNewOrders, 0)} orders
          </span>
        </div>
        <div
          className="w-full h-7 rounded-md overflow-hidden flex"
          style={{
            background: c04Theme.surfaceMuted,
            border: `1px solid ${c04Theme.border}`,
          }}
        >
          {returningPct > 0 && (
            <div
              className="h-full transition-all flex items-center justify-center text-[10px] font-extrabold text-white"
              style={{
                width: `${Math.max(returningPct, 4)}%`,
                background: c04Theme.semantic.positive,
                boxShadow: `inset 0 0 14px ${c04Theme.semantic.positive}99`,
              }}
              title={`${returningPct.toFixed(1)}% from returning customers`}
            >
              {returningPct >= 12 ? `${returningPct.toFixed(0)}%` : ""}
            </div>
          )}
          {newPct > 0 && (
            <div
              className="h-full transition-all flex items-center justify-center text-[10px] font-extrabold text-white"
              style={{
                width: `${Math.max(newPct, 4)}%`,
                background: c04Theme.semantic.brand,
                boxShadow: `inset 0 0 14px ${c04Theme.semantic.brand}99`,
              }}
              title={`${newPct.toFixed(1)}% from new customers`}
            >
              {newPct >= 12 ? `${newPct.toFixed(0)}%` : ""}
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-4 mb-2">
        <span
          className="text-[10px] font-bold uppercase tracking-wider"
          style={{ color: c04Theme.text.faint }}
        >
          Monthly breakdown (supporting trend)
        </span>
      </div>

      <div className="flex-1 min-h-[160px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.2} />
            <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} minTickGap={20} />
            <YAxis tick={{ fontSize: 11, fill: '#888' }} tickLine={false} axisLine={false} />
            <Tooltip content={<InsightTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            <Bar dataKey="returning" stackId="a" fill={c04Theme.semantic.positive} name="Returning" />
            <Bar dataKey="new" stackId="a" fill={c04Theme.semantic.brand} name="New" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </DecisionCardShell>
  );
}
