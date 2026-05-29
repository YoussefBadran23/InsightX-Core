'use client';

/**
 * Customer Segmentation page.
 *
 * Renders A02's RFM output as a "bubble universe" — every segment is a
 * floating glass bubble sized proportional to its customer count and colored
 * by family (champion = gold, loyal = blue, at-risk = red, new = emerald).
 * The bubbles drift via the float keyframes added to tailwind.config.ts.
 *
 * The left sidebar acts as a SLICER. Clicking a segment card filters the
 * bubble universe + the metrics row to that segment only. Clicking the same
 * card again clears the filter. "Export" downloads the currently-selected
 * segment's customer IDs as a CSV (with all selected if no filter).
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Loader2, AlertCircle, Award, ShieldCheck, AlertOctagon, Sparkles, Target,
  X as XIcon, Download,
} from 'lucide-react';
import { analyticsApi } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { useJobStore } from '@/stores/jobStore';
import { t, tp } from '@/lib/i18n';
import { formatMoney } from '@/lib/format';
import { useChartTheme } from '@/components/charts/chartHelpers';

interface SegmentRow {
  segment: string;
  count: number;
  pct: number;
  revenue: number;
  rev_pct: number;
  avg_monetary: number;
}

interface TopCustomer {
  customer_id: string;
  recency_days: number;
  frequency: number;
  monetary: number;
  R: number;
  F: number;
  M: number;
  segment: string;
}

interface RfmResult {
  summary: {
    n_customers: number;
    snapshot_date: string | null;
    total_revenue: number;
    avg_recency: number;
    avg_frequency: number;
    avg_monetary: number;
  };
  segments: SegmentRow[];
  top_customers: TopCustomer[];
}

type Family = 'champion' | 'loyal' | 'risk' | 'new' | 'other';

const SEGMENT_FAMILY: Record<string, Family> = {
  'Champions':           'champion',
  'Loyal Customers':     'loyal',
  'Potential Loyalists': 'loyal',
  'Need Attention':      'loyal',
  'New Customers':       'new',
  'Promising':           'new',
  'About to Sleep':      'risk',
  'At Risk':             'risk',
  'Cannot Lose Them':    'risk',
  'Hibernating':         'risk',
  'Lost':                'risk',
  'Other':               'other',
};

// Bubble visuals per family. Radial gradients are constructed inline so we
// don't need a Tailwind purge whitelist for these dynamic backgrounds.
const FAMILY_VISUAL: Record<Family, { ring: string; bg: string; text: string; icon: any }> = {
  champion: {
    ring: 'ring-amber-200/60',
    bg:   'radial-gradient(circle at 30% 30%, #fcd34d, #d97706)',
    text: 'text-amber-900',
    icon: Award,
  },
  loyal: {
    ring: 'ring-blue-200/60',
    bg:   'radial-gradient(circle at 30% 30%, #93c5fd, #2563eb)',
    text: 'text-blue-50',
    icon: ShieldCheck,
  },
  risk: {
    ring: 'ring-red-200/60',
    bg:   'radial-gradient(circle at 30% 30%, #fca5a5, #dc2626)',
    text: 'text-red-50',
    icon: AlertOctagon,
  },
  new: {
    ring: 'ring-emerald-200/60',
    bg:   'radial-gradient(circle at 30% 30%, #6ee7b7, #059669)',
    text: 'text-emerald-50',
    icon: Sparkles,
  },
  other: {
    ring: 'ring-slate-200/60',
    bg:   'radial-gradient(circle at 30% 30%, #cbd5e1, #64748b)',
    text: 'text-slate-50',
    icon: Sparkles,
  },
};

// Float speed alternates so bubbles drift asynchronously.
const FLOAT_CLASSES = ['animate-float-slow', 'animate-float-medium', 'animate-float-fast'] as const;

export default function SegmentationPage() {
  const language = useUiStore((s) => s.language);
  const currency = useAuthStore((s) => s.user?.preferred_currency) || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const theme = useChartTheme();

  const [data, setData] = useState<RfmResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Slicer state — null = "show all segments". Otherwise the segment name.
  const [selectedSegment, setSelectedSegment] = useState<string | null>(null);

  // ── Drag-and-drop state for the bubble universe ──────────────────────────
  // We track overrides per segment in PERCENT-of-container coordinates so the
  // layout stays correct when the canvas resizes. A bubble keeps its initial
  // spiral position until the user drags it; once moved, the override sticks
  // for the rest of the session.
  const [bubbleOverrides, setBubbleOverrides] = useState<Record<string, { cx: number; cy: number }>>({});
  const [draggingId, setDraggingId] = useState<string | null>(null);
  // Refs hold the per-drag bookkeeping that doesn't need to trigger renders.
  const dragInfoRef = useRef<{
    pointerId: number;
    startX: number; startY: number;   // pointer position when drag began (px)
    startCx: number; startCy: number; // bubble position when drag began (%)
    moved: boolean;
  } | null>(null);
  // Used for click-vs-drag threshold inside the bubble button handlers.
  const universeRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setLoading(true);
    analyticsApi
      .get('rfm')
      .then((res) => {
        const r = res.data?.result_json as RfmResult;
        setData(r);
        setError(null);
      })
      .catch((e) => {
        setError(e?.response?.data?.detail || t('seg_noData', language));
      })
      .finally(() => setLoading(false));
    // language intentionally excluded — only error text uses it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sort segments by count desc so the largest groups read first.
  const sortedSegments = useMemo<SegmentRow[]>(
    () => (data?.segments ?? []).slice().sort((a, b) => b.count - a.count),
    [data],
  );

  // The selected (or default = all) view's customers, used for both the
  // bubble universe overlay and the Export action.
  const filteredCustomers = useMemo(() => {
    const all = data?.top_customers ?? [];
    if (!selectedSegment) return all;
    return all.filter((c) => c.segment === selectedSegment);
  }, [data, selectedSegment]);

  // Bubble layout. Use a deterministic spiral around the center so the
  // largest segment sits in the middle and smaller ones orbit it. Each bubble
  // gets a size proportional to count^0.55 (sub-linear so the biggest doesn't
  // crowd everyone out).
  const bubbleLayout = useMemo(() => {
    const segs = sortedSegments;
    if (segs.length === 0) return [];
    const maxCount = Math.max(...segs.map((s) => s.count), 1);
    // Spiral angles & radii — chosen so 10 bubbles spread without overlap.
    const RADII = [0, 24, 24, 30, 30, 35, 35, 40, 40, 45]; // % from center
    const ANGLES = [0, 30, 210, 110, 290, 70, 250, 150, 330, 190]; // degrees
    return segs.map((s, i) => {
      const sizePct = 14 + (Math.pow(s.count / maxCount, 0.55) * 18); // 14–32 % of container side
      const r = RADII[i] ?? 50;
      const a = ((ANGLES[i] ?? i * 36) * Math.PI) / 180;
      const cx = 50 + r * Math.cos(a);
      const cy = 50 + r * Math.sin(a);
      return {
        segment: s,
        family: SEGMENT_FAMILY[s.segment] ?? 'other',
        sizePct,
        cx, cy,
        floatClass: FLOAT_CLASSES[i % FLOAT_CLASSES.length],
      };
    });
  }, [sortedSegments]);

  // ── Export — downloads the active customer cohort as CSV ────────────────
  const handleCreateCampaign = () => {
    if (!data) return;
    const rows = filteredCustomers;
    const header = ['customer_id', 'segment', 'recency_days', 'frequency', 'monetary', 'R', 'F', 'M'];
    const body = rows.map((c) => [
      c.customer_id, c.segment, c.recency_days, c.frequency, c.monetary, c.R, c.F, c.M,
    ]);
    const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const csv = [header, ...body].map((r) => r.map(esc).join(',')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const stamp = new Date().toISOString().slice(0, 10);
    const slug = (selectedSegment ?? 'all').toLowerCase().replace(/\s+/g, '-');
    a.href = url;
    a.download = `insightx_campaign_${slug}_${stamp}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50 dark:bg-black">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50 dark:bg-black">
        <div className="max-w-md text-center">
          <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-300">{error || 'No data'}</p>
        </div>
      </div>
    );
  }

  // Slicer-aware metrics: when a segment is selected, show that segment's
  // n / revenue / monetary instead of the whole-dataset summary.
  const activeMetrics = (() => {
    if (!selectedSegment) {
      return {
        n: data.summary.n_customers,
        revenue: data.summary.total_revenue,
        avgMonetary: data.summary.avg_monetary,
        avgRecency: data.summary.avg_recency,
      };
    }
    const s = data.segments.find((x) => x.segment === selectedSegment);
    return {
      n: s?.count ?? 0,
      revenue: s?.revenue ?? 0,
      avgMonetary: s?.avg_monetary ?? 0,
      avgRecency: data.summary.avg_recency, // not per-segment in current backend
    };
  })();

  return (
    <div className="flex-1 flex min-w-0 bg-slate-50 dark:bg-black relative z-0 overflow-hidden animate-fade-in">
      <div className="flex-1 flex flex-col p-6 overflow-hidden">
        {/* Header */}
        <div className="mb-4">
          <h1 className="text-gray-900 dark:text-white text-3xl font-bold leading-tight mb-2">
            {t('seg_title', language)}
          </h1>
          <p className="text-slate-500 dark:text-[#9da6b9] text-sm">
            {tp('seg_subtitle', language, {
              n: data.summary.n_customers.toLocaleString(),
              date: data.summary.snapshot_date || '',
            })}
          </p>
          {selectedSegment && (
            <button
              onClick={() => setSelectedSegment(null)}
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
            >
              <XIcon className="w-3 h-3" />
              {t('seg_clearFilter', language)}: <span className="font-semibold">{selectedSegment}</span>
            </button>
          )}
        </div>

        {/* Top metrics — react to the slicer */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-white dark:bg-surface-card rounded-xl border border-slate-200 dark:border-white/10 p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wider text-slate-500">{t('seg_metrics_customers', language)}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              {activeMetrics.n.toLocaleString()}
            </p>
          </div>
          <div className="bg-white dark:bg-surface-card rounded-xl border border-slate-200 dark:border-white/10 p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wider text-slate-500">{t('seg_metrics_revenue', language)}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              {formatMoney(activeMetrics.revenue, currency, { from: sourceCurrency })}
            </p>
          </div>
          <div className="bg-white dark:bg-surface-card rounded-xl border border-slate-200 dark:border-white/10 p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wider text-slate-500">{t('seg_metrics_avgRecency', language)}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              {activeMetrics.avgRecency.toFixed(0)}d
            </p>
          </div>
          <div className="bg-white dark:bg-surface-card rounded-xl border border-slate-200 dark:border-white/10 p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wider text-slate-500">{t('seg_metrics_avgMonetary', language)}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
              {formatMoney(activeMetrics.avgMonetary, currency, { from: sourceCurrency })}
            </p>
          </div>
        </div>

        {/* Bubble universe */}
        <div
            className="flex-1 min-h-[400px] rounded-xl border p-4 relative overflow-hidden shadow-sm flex flex-col transition-colors"
            style={{
              background: theme.surface,
              borderColor: theme.border,
              boxShadow: theme.isDark
                ? '0 1px 0 rgba(255,255,255,0.04) inset, 0 4px 16px rgba(0,0,0,0.25)'
                : '0 1px 3px rgba(15,23,42,0.06)',
            }}
          >
            {/* Universe backdrop — graph-paper grid masked to a soft radial
                vignette so the centre "glows" and the edges fade. The grid
                colour is theme-aware so it stays visible on both light and
                dark surfaces. */}
            <div
              className="absolute inset-0 pointer-events-none transition-opacity"
              style={{
                backgroundImage: `linear-gradient(to right, ${theme.gridStroke} 1px, transparent 1px), linear-gradient(to bottom, ${theme.gridStroke} 1px, transparent 1px)`,
                backgroundSize: '60px 60px',
                maskImage: 'radial-gradient(circle at center, black 30%, transparent 80%)',
                WebkitMaskImage: 'radial-gradient(circle at center, black 30%, transparent 80%)',
                opacity: theme.isDark ? 0.55 : 0.45,
              }}
            />
            {/* Soft brand-tinted glow at the heart of the universe — gives
                the bubble field a sense of "centre of gravity" without
                blocking the chart content. */}
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                background: `radial-gradient(circle at 50% 55%, ${theme.semantic.brand}${theme.isDark ? '22' : '12'} 0%, transparent 55%)`,
              }}
            />

            {/* Title row */}
            <div className="relative flex items-center justify-between mb-4 z-10">
              <h3 className="text-gray-900 dark:text-white font-bold">
                {t('seg_scatterTitle', language)}
              </h3>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500 hidden sm:inline">
                  {selectedSegment
                    ? `${filteredCustomers.length.toLocaleString()} ${t('seg_inSegment', language)}`
                    : `${data.top_customers.length.toLocaleString()} ${t('seg_dataPoints', language)}`}
                </span>
                {Object.keys(bubbleOverrides).length > 0 && (
                  <button
                    onClick={() => setBubbleOverrides({})}
                    className="text-xs font-medium px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
                  >
                    {t('seg_resetPositions', language)}
                  </button>
                )}
              </div>
            </div>

            {/* The bubble field — drag-and-drop enabled. Each bubble lives at
                (cx%, cy%) of this container. The user can drag any bubble to
                reposition; the override is kept in `bubbleOverrides`. A tiny
                movement threshold (4 px) distinguishes click-as-filter from
                click-to-drag so a quick tap still toggles the slicer. */}
            <div
              ref={universeRef}
              className="relative w-full h-[88%] mt-1 select-none touch-none"
              style={{ perspective: '1200px' }}
            >
              {bubbleLayout.map((b, i) => {
                const viz = FAMILY_VISUAL[b.family];
                const Icon = viz.icon;
                const isSelected = selectedSegment === b.segment.segment;
                const dimmed = selectedSegment && !isSelected;
                const override = bubbleOverrides[b.segment.segment];
                const cx = override?.cx ?? b.cx;
                const cy = override?.cy ?? b.cy;
                const isDragging = draggingId === b.segment.segment;
                const wasMoved = !!override;

                const onPointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
                  if (!universeRef.current) return;
                  // Capture so we keep receiving moves even outside the bubble.
                  (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
                  dragInfoRef.current = {
                    pointerId: e.pointerId,
                    startX: e.clientX,
                    startY: e.clientY,
                    startCx: cx,
                    startCy: cy,
                    moved: false,
                  };
                  setDraggingId(b.segment.segment);
                };

                const onPointerMove = (e: React.PointerEvent<HTMLButtonElement>) => {
                  const di = dragInfoRef.current;
                  if (!di || di.pointerId !== e.pointerId || !universeRef.current) return;
                  const rect = universeRef.current.getBoundingClientRect();
                  const dxPct = ((e.clientX - di.startX) / rect.width) * 100;
                  const dyPct = ((e.clientY - di.startY) / rect.height) * 100;
                  // 4 px threshold to suppress accidental drag on a clean click.
                  if (!di.moved && Math.hypot(e.clientX - di.startX, e.clientY - di.startY) > 4) {
                    di.moved = true;
                  }
                  if (!di.moved) return;
                  // Clamp so the bubble stays inside the universe by half its size.
                  const halfSize = b.sizePct / 2;
                  const nextCx = Math.max(halfSize, Math.min(100 - halfSize, di.startCx + dxPct));
                  const nextCy = Math.max(halfSize, Math.min(100 - halfSize, di.startCy + dyPct));
                  setBubbleOverrides((prev) => ({
                    ...prev,
                    [b.segment.segment]: { cx: nextCx, cy: nextCy },
                  }));
                };

                const onPointerUp = (e: React.PointerEvent<HTMLButtonElement>) => {
                  const di = dragInfoRef.current;
                  if (!di) return;
                  (e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId);
                  const wasDrag = di.moved;
                  dragInfoRef.current = null;
                  setDraggingId(null);
                  // No drag → treat as a click → toggle the slicer.
                  if (!wasDrag) {
                    setSelectedSegment((prev) =>
                      prev === b.segment.segment ? null : b.segment.segment,
                    );
                  }
                };

                return (
                  <button
                    key={b.segment.segment}
                    type="button"
                    onPointerDown={onPointerDown}
                    onPointerMove={onPointerMove}
                    onPointerUp={onPointerUp}
                    onPointerCancel={onPointerUp}
                    // Suppress the synthetic click since onPointerUp handles it.
                    onClick={(e) => e.preventDefault()}
                    className={`absolute rounded-full ${viz.text} ring-4 ${viz.ring}
                      transition-shadow duration-300 flex flex-col items-center
                      justify-center text-center px-2 hover:z-50
                      ${isSelected ? 'ring-8 ring-offset-2 z-40' : ''}
                      ${dimmed ? 'opacity-30' : ''}
                      ${isDragging ? 'cursor-grabbing z-50 shadow-2xl' : 'cursor-grab'}
                      ${!wasMoved && !isDragging ? b.floatClass : ''}`}
                    style={{
                      // Anchor at top-left so the float animation's `transform`
                      // doesn't fight a centering transform. Half-size offset
                      // centers the visible disc on (cx, cy).
                      left: `calc(${cx}% - ${b.sizePct / 2}%)`,
                      top:  `calc(${cy}% - ${b.sizePct / 2}%)`,
                      width: `${b.sizePct}%`,
                      aspectRatio: '1',
                      background: viz.bg,
                      boxShadow: isDragging
                        ? 'inset -4px -4px 8px rgba(0,0,0,0.15), inset 4px 4px 8px rgba(255,255,255,0.7), 0 18px 35px rgba(0,0,0,0.25)'
                        : 'inset -4px -4px 8px rgba(0,0,0,0.1), inset 4px 4px 8px rgba(255,255,255,0.6), 0 8px 15px rgba(0,0,0,0.15)',
                      animationDelay: `${i * 0.3}s`,
                      touchAction: 'none',
                    }}
                    title={`${b.segment.segment} · ${b.segment.count.toLocaleString()} customers — ${t('seg_dragHint', language)}`}
                    aria-label={`${b.segment.segment} (${b.segment.count.toLocaleString()} customers) — drag to reposition, click to filter`}
                  >
                    <Icon className="w-5 h-5 mb-1 drop-shadow pointer-events-none" />
                    <span className="text-[10px] sm:text-xs font-bold leading-tight drop-shadow pointer-events-none">
                      {b.segment.segment}
                    </span>
                    <span className="text-[10px] font-semibold opacity-90 drop-shadow pointer-events-none">
                      {b.segment.count.toLocaleString()}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Legend */}
            <div className="absolute bottom-3 left-4 flex flex-wrap gap-3 text-[11px] text-slate-500 dark:text-slate-400 z-10">
              <div className="flex items-center gap-1.5">
                <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#d97706' }} />
                {t('seg_familyChampion', language)}
              </div>
              <div className="flex items-center gap-1.5">
                <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#2563eb' }} />
                {t('seg_familyLoyal', language)}
              </div>
              <div className="flex items-center gap-1.5">
                <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#059669' }} />
                {t('seg_familyNew', language)}
              </div>
              <div className="flex items-center gap-1.5">
                <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: '#dc2626' }} />
                {t('seg_familyRisk', language)}
              </div>
            </div>
          </div>
      </div>

      {/* Right sidebar — real segments, now a clickable slicer */}
      <aside className="hidden xl:flex w-[360px] bg-white dark:bg-surface-card border-s border-slate-200 dark:border-white/10 flex-col shrink-0 z-10 shadow-2xl">
        <div className="p-6 border-b border-slate-200 dark:border-white/10">
          <h2 className="text-gray-900 dark:text-white text-lg font-bold mb-1">{t('seg_sidebarTitle', language)}</h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            {data.summary.n_customers.toLocaleString()} {t('seg_sidebarSubtitle', language)}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {sortedSegments.map((s) => {
            const family = SEGMENT_FAMILY[s.segment] ?? 'other';
            const viz = FAMILY_VISUAL[family];
            const Icon = viz.icon;
            const isSelected = selectedSegment === s.segment;
            const familyBorder =
              family === 'champion' ? 'border-amber-500' :
              family === 'loyal'    ? 'border-blue-500'  :
              family === 'risk'     ? 'border-red-500'   :
              family === 'new'      ? 'border-emerald-500' :
                                      'border-slate-400';
            const familyColor =
              family === 'champion' ? '#d97706' :
              family === 'loyal'    ? '#2563eb' :
              family === 'risk'     ? '#dc2626' :
              family === 'new'      ? '#059669' :
                                      '#64748b';
            return (
              <button
                key={s.segment}
                onClick={() => setSelectedSegment((prev) => prev === s.segment ? null : s.segment)}
                className={`w-full text-left bg-slate-50 dark:bg-black/30 hover:bg-slate-100 dark:hover:bg-white/5
                  border-s-4 ${familyBorder} rounded-xl p-4 shadow-sm transition-all cursor-pointer border border-transparent
                  ${isSelected
                    ? 'ring-2 ring-primary/60 bg-primary/5 dark:bg-primary/10 shadow-md border-primary/20'
                    : 'dark:border-white/5'}`}
                aria-pressed={isSelected}
              >
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-2">
                    <Icon className="w-5 h-5" style={{ color: familyColor }} />
                    <h3 className="text-gray-900 dark:text-white font-semibold">{s.segment}</h3>
                  </div>
                  <span
                    className="text-xs px-2 py-1 rounded font-medium"
                    style={{ background: `${familyColor}22`, color: familyColor }}
                  >
                    {s.pct.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between items-end mb-2">
                  <span className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">
                    {s.count.toLocaleString()}
                  </span>
                  <span className="text-sm text-slate-500">{t('seg_customers', language)}</span>
                </div>
                <div className="space-y-1 mt-2">
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{t('seg_avgLtv', language)}</span>
                    <span className="text-gray-900 dark:text-white font-mono">
                      {formatMoney(s.avg_monetary, currency, { from: sourceCurrency })}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{t('seg_revShare', language)}</span>
                    <span className="text-gray-900 dark:text-white font-mono">{s.rev_pct.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-[#111318] rounded-full h-1.5 overflow-hidden mt-1.5">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${Math.min(100, s.rev_pct)}%`, background: familyColor }}
                    />
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="p-6 pt-4 border-t border-slate-200 dark:border-white/10 bg-white dark:bg-surface-card">
          <button
            onClick={handleCreateCampaign}
            className="w-full bg-primary hover:bg-primary-hover text-white font-medium h-12 rounded-lg transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2 cursor-pointer"
            title={selectedSegment
              ? `Export (${selectedSegment})`
              : t('seg_exportAll', language)}
          >
            {selectedSegment
              ? <><Download className="w-5 h-5" /> Export</>
              : <><Download className="w-5 h-5" /> {t('seg_exportAll', language)}</>}
          </button>
          {selectedSegment && (
            <p className="text-[11px] text-slate-500 text-center mt-2">
              {tp('seg_campaignHint', language, { n: filteredCustomers.length.toLocaleString(), seg: selectedSegment })}
            </p>
          )}
        </div>
      </aside>
    </div>
  );
}
