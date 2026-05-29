import { useMemo } from "react";
import {
  ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, Tooltip, CartesianGrid, ZAxis,
  ComposedChart, Area, Line, ReferenceDot,
} from "recharts";
import { InsightCard } from "./foundation/InsightCard";
import { InsightTooltip } from "./foundation/InsightTooltip";
import { DecisionCardShell } from "./foundation/DecisionCardShell";
import { AIInsightPanel } from "./foundation/AIInsightPanel";
import { ActionChipRow, type SuggestedAction } from "./foundation/ActionChipRow";

import { fmtCompact, paletteColor, NoDataState, TOOLTIP_STYLE, heatColor, useChartTheme } from "./chartHelpers";

/* ── A16 Anomaly Detection · Decision-Chart v1 ───────────────────────────
   Question: "Did anything unusual happen in my sales recently?"        */
export function A16AnomalyChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const theme = useChartTheme();
  const series: any[] = data?.series || data?.daily || data?.timeseries || [];
  const anomalies: any[] = data?.anomalies || [];

  const rows = useMemo(() => {
    if (series.length === 0) return [];
    const anomMap = new Map<string, any>();
    anomalies.forEach((a) => anomMap.set(String(a.date || a.period || ""), a));
    return series.map((p: any) => {
      const date = String(p.date || p.period || p.x || "");
      const value = Number(p.value ?? p.revenue ?? p.y ?? 0);
      const lower = Number(p.expected_lower ?? p.lower ?? value * 0.7);
      const upper = Number(p.expected_upper ?? p.upper ?? value * 1.3);
      const anom = anomMap.get(date);
      return {
        date,
        value,
        band: [lower, upper] as [number, number],
        anomaly: anom ? value : null,
        anomaly_meta: anom || null,
      };
    });
  }, [series, anomalies]);

  const headline = data?.headline ?? {};
  const summary = data?.summary ?? {};
  const question = data?.question || "Did anything unusual happen in my sales recently?";
  const anomalyCount = anomalies.length;
  const headlineValue = Number(headline.value ?? summary.n_anomalies ?? anomalyCount);

  if (rows.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A16"
        question={question}
        period="no data"
        headlineValue="0"
        headlineLabel="anomalies detected"
        trendPct={null}
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState message="No anomaly data yet" />
      </DecisionCardShell>
    );
  }

  const yMax = Math.max(...rows.map((r) => Math.max(r.value, r.band[1])), 100);

  const headerRight = anomalyCount > 0 ? (
    <div
      className="px-2 py-1 rounded-md flex items-center gap-1.5"
      style={{
        background: theme.semanticSoft.danger,
        border: `1px solid ${theme.semantic.danger}40`,
      }}
    >
      <span style={{ color: theme.semantic.danger }}>⚠</span>
      <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: theme.semantic.danger }}>
        {anomalyCount} flagged
      </span>
    </div>
  ) : null;

  return (
    <DecisionCardShell
      moduleKey="A16"
      question={question}
      period={headline.period || "Daily rolling window"}
      headlineValue={headlineValue.toLocaleString()}
      headlineLabel={headline.label || "anomalies detected"}
      trendPct={null}
      headerRight={headerRight}
      headlineKind={headlineValue >= 3 ? "danger" : headlineValue >= 1 ? "warning" : "positive"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex flex-col h-full w-full pt-1">
        <div className="flex flex-wrap gap-4 px-2 pb-2 text-[11px]">
          <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-300">
            <span className="w-3 h-3 rounded-sm" style={{ background: theme.isDark ? "rgba(218,226,255,0.15)" : "rgba(43,108,238,0.1)", border: `1px solid ${theme.primary}` }} />
            Expected Range
          </span>
          <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-300">
            <span className="w-4 h-0.5" style={{ background: theme.primary }} />
            Actual Trend
          </span>
          <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-300">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500" style={{ boxShadow: "0 0 8px rgba(225,29,72,0.6)" }} />
            Anomalies
          </span>
        </div>

        <div className="flex-1 min-h-[260px] pb-2">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 16, right: 16, left: 4, bottom: 8 }}>
              <defs>
                <linearGradient id="a16-band" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor={theme.primary} stopOpacity={0.15} />
                  <stop offset="100%" stopColor={theme.primary} stopOpacity={0.02} />
                </linearGradient>
                <filter id="a16-line-glow" x="-10%" y="-30%" width="120%" height="160%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>
              <CartesianGrid stroke={theme.gridStroke} strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: theme.axisColor }}
                tickLine={false}
                axisLine={{ stroke: theme.gridStroke }}
                minTickGap={36}
              />
              <YAxis
                tick={{ fontSize: 10, fill: theme.axisColor }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => fmtCompact(Number(v))}
                width={50}
                domain={[0, yMax * 1.1]}
              />
              <Tooltip
                content={<InsightTooltip />}
                cursor={{ stroke: "rgba(225,29,72,0.4)", strokeDasharray: "2 2", strokeWidth: 1 }}
                formatter={(v: any, name: string, item: any) => {
                  if (v == null) return ["—", name];
                  if (name === "band") return [`${fmtCompact(v[0])} – ${fmtCompact(v[1])}`, "Expected"];
                  if (name === "anomaly") {
                    const meta = item.payload.anomaly_meta;
                    return [
                      `${fmtCompact(Number(v))}${meta ? ` (z=${Number(meta.z_score || 0).toFixed(1)})` : ""}`,
                      meta?.type === "low" ? "Critical Dip" : "Critical Spike",
                    ];
                  }
                  return [fmtCompact(Number(v)), "Actual"];
                }}
              />
              <Area
                type="monotone"
                dataKey="band"
                stroke="none"
                fill="url(#a16-band)"
                isAnimationActive={false}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke={theme.primary}
                strokeWidth={3}
                dot={false}
                isAnimationActive={false}
                filter="url(#a16-line-glow)"
              />
              <Scatter
                dataKey="anomaly"
                fill="#e11d48"
                shape={(props: any) => {
                  const { cx, cy } = props;
                  if (cy == null) return <g />;
                  return (
                    <g>
                      <circle cx={cx} cy={cy} r={14} fill="rgba(225,29,72,0.2)" className="animate-pulse" />
                      <circle cx={cx} cy={cy} r={5} fill="#e11d48" stroke="#fff" strokeWidth={2} />
                    </g>
                  );
                }}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </DecisionCardShell>
  );
}

/* ── A03 Market Basket · Decision-Chart v1 ──────────────────────────────
   Question: "What do my customers buy together?"                      */
export function A03MarketBasketChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const pairs: any[] = data?.top_pairs || [];
  const topProducts: any[] = data?.top_products || [];
  const headline = data?.headline ?? {};
  const question = data?.question || "What do my customers buy together?";

  const { nodes, edges } = useMemo(() => {
    if (pairs.length === 0) return { nodes: [], edges: [] };
    const linkedIds: string[] = [];
    const seen = new Set<string>();
    for (const p of pairs) {
      for (const id of [p.antecedent, p.consequent]) {
        if (!seen.has(id)) { seen.add(id); linkedIds.push(id); }
        if (linkedIds.length >= 7) break;
      }
      if (linkedIds.length >= 7) break;
    }
    if (linkedIds.length === 0) return { nodes: [], edges: [] };

    const freqMap = new Map<string, { freq: number; support: number; name?: string }>(
      topProducts.map((p: any) => [p.product_id, {
        freq: Number(p.frequency) || 0,
        support: Number(p.support) || 0,
        name: p.name,
      }]),
    );

    const cx = 250, cy = 250, R = 160;
    const orbit = linkedIds.slice(1, 7);
    const center = linkedIds[0];

    const nodesOut = [
      {
        id: center,
        x: cx, y: cy,
        display: (freqMap.get(center)?.name || center).slice(0, 16),
        support: freqMap.get(center)?.support ?? 0,
        isCenter: true,
      },
      ...orbit.map((id, i) => {
        const angle = (i / Math.max(orbit.length, 1)) * 2 * Math.PI - Math.PI / 2;
        return {
          id,
          x: cx + R * Math.cos(angle),
          y: cy + R * Math.sin(angle),
          display: (freqMap.get(id)?.name || id).slice(0, 16),
          support: freqMap.get(id)?.support ?? 0,
          isCenter: false,
        };
      }),
    ];

    const nodeIdx = new Map(nodesOut.map((n) => [n.id, n]));
    const edgesOut = pairs
      .filter((p) => nodeIdx.has(p.antecedent) && nodeIdx.has(p.consequent))
      .slice(0, 20)
      .map((p) => ({
        a: nodeIdx.get(p.antecedent)!,
        b: nodeIdx.get(p.consequent)!,
        lift: Number(p.lift) || 0,
        confidence: Number(p.confidence) || 0,
        support: Number(p.support) || 0,
        antName: p.antecedent_name || p.antecedent,
        conName: p.consequent_name || p.consequent,
      }));
    return { nodes: nodesOut, edges: edgesOut };
  }, [pairs, topProducts]);

  const topRule = pairs[0];

  if (pairs.length === 0 || nodes.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A03"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="product pairs found"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState message="Not enough co-occurring pairs to build a network." />
      </DecisionCardShell>
    );
  }

  const edgeStyle = (lift: number) => {
    if (lift >= 2.0)  return { stroke: "url(#a03-strong)", width: 3.5, dash: "",     opacity: 0.9, label: "Strong" };
    if (lift >= 1.2)  return { stroke: "#0053cd",         width: 2,   dash: "",     opacity: 0.5, label: "Moderate" };
    return                    { stroke: "#737686",        width: 1,   dash: "4 4",  opacity: 0.4, label: "Weak" };
  };

  const topLift = topRule ? Number(topRule.lift ?? 0) : 0;

  return (
    <DecisionCardShell
      moduleKey="A03"
      question={question}
      period={headline.period || `${pairs.length} pairs analysed`}
      headlineValue={topLift > 0 ? `${topLift.toFixed(2)}×` : String(pairs.length)}
      headlineLabel={topLift > 0 ? "strongest pair lift" : "product pairs found"}
      headlineKind={topLift >= 2 ? "positive" : "neutral"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      {/* ── Direct-answer top-pairs list ─────────────────────────────
          Question is "what do they buy together?" — the literal answer
          is a list of pairs. The network graph below is interactive
          evidence but this strip is the read-it-in-one-second answer. */}
      <div className="mb-3 space-y-1">
        {pairs.slice(0, 3).map((p: any, i: number) => {
          const liftN = Number(p.lift || 0);
          const strong = liftN >= 2;
          const mod = liftN >= 1.2 && liftN < 2;
          const accent = strong ? "#10b981" : mod ? "#0053cd" : "#737686";
          const bg = i === 0 ? "rgba(0,83,205,0.10)" : "rgba(148,163,184,0.08)";
          const aName = String(p.antecedent_name || p.antecedent || "").slice(0, 28);
          const bName = String(p.consequent_name || p.consequent || "").slice(0, 28);
          return (
            <div
              key={`${p.antecedent}->${p.consequent}-${i}`}
              className="flex items-center gap-2.5 rounded-md px-2.5 py-1.5"
              style={{
                background: bg,
                border: `1px solid ${accent}33`,
              }}
            >
              <span
                className="text-[10px] font-extrabold w-4 text-center tabular-nums"
                style={{ color: accent }}
              >
                {i + 1}
              </span>
              <span
                className="text-[11.5px] font-semibold flex-1 truncate"
                style={{ color: "currentColor" }}
              >
                <span className="font-bold">{aName}</span>
                <span className="mx-1.5 opacity-60">→</span>
                <span className="font-bold">{bName}</span>
              </span>
              <span
                className="text-[11px] font-extrabold tabular-nums shrink-0"
                style={{ color: accent }}
              >
                {liftN.toFixed(2)}×
              </span>
              <span
                className="text-[9.5px] tabular-nums shrink-0 opacity-70"
              >
                {((p.confidence || 0) * 100).toFixed(0)}% conf
              </span>
            </div>
          );
        })}
      </div>

      <div className="flex-1 min-h-0 flex flex-col md:flex-row py-2">
        <div className="flex-1 min-h-[260px] p-3 flex items-center justify-center">
          <svg viewBox="0 0 500 500" className="w-full h-full max-h-[420px]">
            <defs>
              <linearGradient id="a03-strong" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%"  stopColor="#0053cd" />
                <stop offset="100%" stopColor="#a855f7" />
              </linearGradient>
              <filter id="a03-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {edges.map((e, i) => {
              const st = edgeStyle(e.lift);
              const mx = (e.a.x + e.b.x) / 2;
              const my = (e.a.y + e.b.y) / 2;
              const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y;
              const len = Math.hypot(dx, dy) || 1;
              const off = 30 * (i % 2 === 0 ? 1 : -1);
              const cx = mx - (dy / len) * off;
              const cy = my + (dx / len) * off;
              return (
                <path
                  key={`e${i}`}
                  d={`M ${e.a.x} ${e.a.y} Q ${cx} ${cy} ${e.b.x} ${e.b.y}`}
                  fill="none"
                  stroke={st.stroke}
                  strokeWidth={st.width}
                  strokeOpacity={st.opacity}
                  strokeDasharray={st.dash}
                  strokeLinecap="round"
                >
                  <title>{`${e.antName} ↔ ${e.conName} · lift ${e.lift.toFixed(2)}x · conf ${(e.confidence * 100).toFixed(0)}%`}</title>
                </path>
              );
            })}

            {nodes.map((n) => {
              const r = n.isCenter ? 40 : 22 + Math.min(18, n.support * 60);
              const stroke = n.isCenter ? "#2b6cee" : "#0053cd";
              return (
                <g key={n.id}>
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r={r}
                    fill={n.isCenter ? "#f2f3fe" : "#ffffff"}
                    stroke={stroke}
                    strokeWidth={n.isCenter ? 4 : 2}
                    filter={n.isCenter ? "url(#a03-glow)" : undefined}
                  >
                    <title>{n.display}</title>
                  </circle>
                  <text
                    x={n.x}
                    y={n.y + 4}
                    textAnchor="middle"
                    fontSize={n.isCenter ? 13 : 11}
                    fontWeight={700}
                    fill={n.isCenter ? "#0053cd" : "#0f172a"}
                    style={{ pointerEvents: "none" }}
                  >
                    {n.display.length > 12 ? n.display.slice(0, 11) + "…" : n.display}
                  </text>
                  {n.support > 0 && (
                    <text
                      x={n.x}
                      y={n.y + (n.isCenter ? 20 : 18)}
                      textAnchor="middle"
                      fontSize={10}
                      fill="#64748b"
                      style={{ pointerEvents: "none" }}
                    >
                      {(n.support * 100).toFixed(0)}%
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        <aside className="w-full md:w-60 flex-shrink-0 p-4 bg-slate-50/50 dark:bg-white/[0.02] rounded-xl border border-slate-100 dark:border-white/5 flex flex-col gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
              Connection Strength (Lift)
            </p>
            <ul className="space-y-2 text-[11px]">
              <li className="flex items-center gap-2">
                <span className="inline-block w-8 h-1 rounded" style={{ background: "linear-gradient(to right, #0053cd, #a855f7)" }} />
                <span className="text-slate-800 dark:text-slate-200 font-medium">Strong (≥ 2.0×)</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block w-8 h-0.5 rounded bg-[#0053cd] opacity-50" />
                <span className="text-slate-800 dark:text-slate-200 font-medium">Moderate (1.2–2.0×)</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block w-8 border-t-2 border-dashed border-slate-400" />
                <span className="text-slate-800 dark:text-slate-200 font-medium">Weak (&lt; 1.2×)</span>
              </li>
            </ul>
          </div>

          {topRule && (
            <div className="bg-white dark:bg-surface-card rounded-lg p-3 border border-slate-200 dark:border-white/10 shadow-sm mt-auto">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                Top Association Rule
              </p>
              <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                <span className="text-xs font-bold text-slate-900 dark:text-white truncate max-w-[80px]">
                  {topRule.antecedent_name || topRule.antecedent}
                </span>
                <span className="text-slate-400">→</span>
                <span className="text-xs font-bold text-violet-600 dark:text-violet-400 truncate max-w-[80px]">
                  {topRule.consequent_name || topRule.consequent}
                </span>
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-snug">
                Customers buying this are <strong className="text-slate-900 dark:text-white font-bold">{Number(topRule.lift).toFixed(2)}×</strong> more likely to also purchase the linked item.
                <span className="block mt-1 text-[10px] text-slate-400 font-medium">
                  Confidence {(Number(topRule.confidence) * 100).toFixed(0)}% · Support {(Number(topRule.support) * 100).toFixed(1)}%
                </span>
              </p>
            </div>
          )}
        </aside>
      </div>
    </DecisionCardShell>
  );
}

/* ── A06 Geographic Revenue · Decision-Chart v1 ─────────────────────────
   Question: "Where in the country are my orders coming from?"        */
export function A06GeographicChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const theme = useChartTheme();
  const list = data?.by_country?.length ? data.by_country
    : data?.by_region?.length ? data.by_region
    : data?.by_city || [];
  const headline = data?.headline ?? {};
  const question = data?.question || "Where in the country are my orders coming from?";

  if (list.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="A06"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="regions with sales"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState />
      </DecisionCardShell>
    );
  }
  const keyField = data?.by_country?.length ? "country" : data?.by_region?.length ? "region" : "customer_city";
  const rows = list.slice(0, 15);
  const max = Math.max(...rows.map((r: any) => Number(r.revenue || 0)), 1);

  const regionAnchors: Record<string, { x: number; y: number; r: number }> = {
    "north america": { x: 220, y: 180, r: 80 },
    "na":            { x: 220, y: 180, r: 80 },
    "europe":        { x: 520, y: 120, r: 60 },
    "eu":            { x: 520, y: 120, r: 60 },
    "asia pacific":  { x: 820, y: 220, r: 70 },
    "apac":          { x: 820, y: 220, r: 70 },
    "latin america": { x: 320, y: 360, r: 55 },
    "latam":         { x: 320, y: 360, r: 55 },
    "africa":        { x: 540, y: 320, r: 45 },
    "middle east":   { x: 600, y: 240, r: 50 },
    "mea":           { x: 600, y: 240, r: 50 },
  };
  const top3 = rows.slice(0, 3);

  const topItem = rows[0];
  const topName = topItem ? String(topItem[keyField] || topItem.name || "—") : "—";

  return (
    <DecisionCardShell
      moduleKey="A06"
      question={question}
      period={headline.period || `${list.length} regions tracked`}
      headlineValue={topName.slice(0, 22)}
      headlineLabel={headline.label || "top region by revenue"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row py-2">
        <div className="flex-1 min-h-[300px] p-2 relative">
          <div className="relative w-full h-full bg-slate-50 dark:bg-black/30 rounded-xl overflow-hidden border border-slate-200 dark:border-white/5 flex items-center justify-center">
            <svg viewBox="0 0 1000 500" className="w-full h-full">
              <defs>
                <filter id="a06-blur" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur stdDeviation="20" />
                </filter>
              </defs>
              <g fill={theme.isDark ? "rgba(148,163,184,0.10)" : "rgba(148,163,184,0.20)"}>
                <path d="M100,150 Q120,130 180,120 Q220,110 280,80 Q320,60 380,50 L400,100 L380,150 Q360,180 300,220 Q250,250 200,280 Q180,320 150,380 L100,420 Z" />
                <path d="M450,80 Q480,50 550,60 Q600,70 650,40 L700,90 Q680,120 620,150 Q580,180 520,160 Z" />
                <path d="M750,100 Q800,80 850,120 Q900,160 950,200 L900,300 Q850,350 800,320 Q750,280 720,200 Z" />
                <path d="M480,220 Q520,200 580,240 Q620,280 600,350 L550,450 Q500,400 450,320 Z" />
                <path d="M700,350 Q750,320 800,380 Q850,420 820,480 L780,450 Z" />
              </g>

              {rows.slice(0, 6).map((r: any, i: number) => {
                const v = Number(r.revenue || 0);
                const intensity = v / max;
                const anchor = regionAnchors[String(r[keyField] || "").toLowerCase()];
                if (!anchor) return null;
                return (
                  <circle
                    key={`g${i}`}
                    cx={anchor.x}
                    cy={anchor.y}
                    r={anchor.r}
                    fill={theme.primary}
                    opacity={0.10 + intensity * 0.25}
                    filter="url(#a06-blur)"
                  />
                );
              })}

              {top3.map((r: any, i: number) => {
                const anchor = regionAnchors[String(r[keyField] || "").toLowerCase()];
                if (!anchor) return null;
                return (
                  <g key={`m${i}`} transform={`translate(${anchor.x}, ${anchor.y})`}>
                    <circle r="14" fill={theme.primary} opacity="0.20" className="animate-ping origin-center" />
                    <circle r="5" fill={theme.primary} />
                    <circle r="2" fill="#fff" />
                  </g>
                );
              })}
            </svg>

            {top3[0] && (() => {
              const r = top3[0];
              const v = Number(r.revenue || 0);
              const pct = (v / max) * 100;
              return (
                <div className="absolute top-4 right-4 bg-white/95 dark:bg-surface-elevated/95 backdrop-blur border border-slate-200 dark:border-white/10 rounded-xl shadow-xl p-3 w-56">
                  <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 dark:border-white/5">
                    <span className="text-[12px] font-bold flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full shadow-sm" style={{ background: theme.primary }} />
                      {r[keyField]}
                    </span>
                    <span className="text-[10px] font-bold text-slate-400">TOP</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-600 dark:text-slate-300 mb-1 font-medium">
                    <span>Revenue</span>
                    <span className="font-bold text-slate-900 dark:text-white">${fmtCompact(v)}</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-600 dark:text-slate-300 font-medium">
                    <span>Share</span>
                    <span className="text-emerald-600 dark:text-emerald-400 font-bold">{pct.toFixed(0)}%</span>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>

        <aside className="w-full lg:w-72 mt-4 lg:mt-0 lg:ml-6 flex flex-col">
          <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4 flex items-center gap-2">
            <span className="w-1.5 h-4 rounded-sm" style={{ background: theme.primary }} /> Top Regions
          </h4>
          <div className="flex flex-col gap-5 flex-1">
            {rows.slice(0, 5).map((r: any, i: number) => {
              const v = Number(r.revenue || 0);
              const total = rows.reduce((s: number, x: any) => s + Number(x.revenue || 0), 0);
              const pct = total > 0 ? (v / total) * 100 : 0;
              return (
                <div key={r[keyField] || i}>
                  <div className="flex items-end justify-between mb-2">
                    <span className="text-xs font-bold truncate text-slate-800 dark:text-slate-200">{r[keyField]}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">${fmtCompact(v)}</span>
                      <span className="text-[10px] font-black px-1.5 py-0.5 rounded-sm" style={{ color: theme.primary, backgroundColor: `${theme.primary}15` }}>
                        {pct.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <div className="w-full h-2 rounded-full overflow-hidden bg-slate-100 dark:bg-white/5">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.max(2, pct)}%`,
                        background: `linear-gradient(90deg, ${theme.primary}, ${i === 0 ? "#a855f7" : theme.primary})`,
                        opacity: 0.9 - (i * 0.1),
                        boxShadow: `0 0 10px ${theme.primary}40`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </aside>
      </div>
    </DecisionCardShell>
  );
}

/* ── C03 Geographic Distribution · Decision-Chart v1 ────────────────────
   Question: "Where are my customers concentrated on the map?"        */
export function C03GeoDistributionChart({ data, moduleKey }: { data: any; moduleKey: string }) {
  const list = data?.by_country?.length ? data.by_country
    : data?.by_region?.length ? data.by_region
    : data?.by_city || [];
  const headline = data?.headline ?? {};
  const question = data?.question || "Where are my customers concentrated on the map?";
  if (list.length === 0) {
    return (
      <DecisionCardShell
        moduleKey="C03"
        question={question}
        period="no data"
        headlineValue="—"
        headlineLabel="locations with customers"
        aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
        actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
      >
        <NoDataState />
      </DecisionCardShell>
    );
  }
  const keyField = data?.by_country?.length ? "country" : data?.by_region?.length ? "region" : "customer_city";
  const rows = list.slice(0, 15);
  const max = Math.max(...rows.map((r: any) => Number(r.customers || 0)), 1);
  const topItem = rows[0];
  const topName = topItem ? String(topItem[keyField] || topItem.name || "—") : "—";
  return (
    <DecisionCardShell
      moduleKey="C03"
      question={question}
      period={headline.period || `${list.length} locations`}
      headlineValue={topName.slice(0, 22)}
      headlineLabel={headline.label || "top location by customers"}
      aiInsight={<AIInsightPanel moduleKey={moduleKey} question={question} data={data} />}
      actions={<ActionChipRow actions={(data?.suggested_actions as SuggestedAction[]) || []} />}
    >
      <div className="w-full h-full py-2 overflow-auto">
        <ul className="space-y-3 text-[11px] px-2">
          {rows.map((r: any, i: number) => {
            const v = Number(r.customers || 0);
            const pct = (v / max) * 100;
            return (
              <li key={r[keyField] || i} className="flex items-center gap-3">
                <span className="w-28 font-bold truncate text-slate-700 dark:text-slate-300" title={r[keyField]}>
                  {r[keyField]}
                </span>
                <div className="flex-1 h-2.5 rounded-full overflow-hidden bg-slate-100 dark:bg-white/5">
                  <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: paletteColor(i) }} />
                </div>
                <span className="w-12 text-right font-mono font-medium text-slate-500">{v.toLocaleString()}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </DecisionCardShell>
  );
}
