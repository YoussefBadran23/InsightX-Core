"use client";

/**
 * Generic wrapper around any chart component. Owns:
 *   - the card chrome (title, info tooltip, remove button in customise mode)
 *   - data fetching from the analytics summary endpoint
 *   - polished loading / error / empty / no-data states
 *
 * The actual chart is resolved via `chartRegistry[module_key]`. New chart
 * components only need to handle "given this result JSON, render the SVG /
 * canvas" — fetching and chrome are handled here.
 */

import { memo, startTransition, useEffect, useRef, useState } from "react";
import { X, AlertCircle, Info, Inbox } from "lucide-react";

import { analyticsApi } from "@/lib/api";
import { useUiStore } from "@/stores/uiStore";
import { useDashboardStore } from "@/stores/dashboardStore";
import { MODULES_BY_KEY } from "@/lib/modulesCatalog";

import { chartRegistry } from "./chartRegistry";
import { InsightCard } from "./foundation/InsightCard";
import { ChartExportMenu } from "./foundation/ChartExportMenu";

interface ChartCardProps {
  widgetId: string;
  moduleKey: string;
  jobId: string | null;
  /**
   * Optional pre-fetched module result. When the parent (Analytics page) has
   * already fetched `/analytics/summary` once for the whole grid, it passes
   * each module's slice in here so this card skips its own network call.
   * Pass `null` explicitly to mean "the parent ran the fetch but this module
   * had no data" — that's different from `undefined` ("nothing pre-fetched").
   */
  preloadedData?: unknown | null;
}

function ChartSkeleton() {
  return (
    <div className="w-full h-full p-4 flex items-end gap-2 animate-pulse">
      <div className="flex-1 bg-slate-200 dark:bg-slate-700/40 rounded" style={{ height: "60%" }} />
      <div className="flex-1 bg-slate-200 dark:bg-slate-700/40 rounded" style={{ height: "85%" }} />
      <div className="flex-1 bg-slate-200 dark:bg-slate-700/40 rounded" style={{ height: "40%" }} />
      <div className="flex-1 bg-slate-200 dark:bg-slate-700/40 rounded" style={{ height: "70%" }} />
      <div className="flex-1 bg-slate-200 dark:bg-slate-700/40 rounded" style={{ height: "55%" }} />
      <div className="flex-1 bg-slate-200 dark:bg-slate-700/40 rounded" style={{ height: "90%" }} />
    </div>
  );
}

function NoDataEmpty({ description }: { description: string }) {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center px-6 text-center py-6">
      <div className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-3">
        <Inbox className="w-5 h-5 text-slate-400" />
      </div>
      <p className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-1">No data yet</p>
      <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-[28ch] leading-snug">{description}</p>
    </div>
  );
}

function ErrorEmpty({ message }: { message: string }) {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center px-6 text-center py-6">
      <AlertCircle className="w-8 h-8 text-amber-500 mb-2" />
      <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">{message}</p>
    </div>
  );
}

function ChartCardInner({ widgetId, moduleKey, jobId, preloadedData }: ChartCardProps) {
  const language = useUiStore((s) => s.language);
  const isCustomizing = useDashboardStore((s) => s.isCustomizing);
  const removeWidget = useDashboardStore((s) => s.removeWidget);

  // ── Lazy render via IntersectionObserver ─────────────────────────────────
  // Show a lightweight skeleton until the card scrolls into view (plus 200 px
  // margin so charts just below the fold pre-render before they're visible).
  // Once triggered we disconnect — charts never revert to skeleton on scroll.
  const cardRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const el = cardRef.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setIsVisible(true); // SSR / old browser fallback: render immediately
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          // startTransition marks the chart mount as low-priority so React
          // yields to the browser between frames and keeps scroll smooth.
          startTransition(() => setIsVisible(true));
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Fast path: if the parent supplied `preloadedData` (analytics page batches
  // a single `/analytics/summary` call and slices it out per widget), we skip
  // the per-card network call entirely. `preloadedData === undefined` keeps
  // the old behaviour for callers that haven't been upgraded yet (e.g. the
  // dashboard home's "My Custom Charts" strip).
  const hasPreload = preloadedData !== undefined;

  const [data, setData] = useState<any>(hasPreload ? preloadedData : null);
  const [loading, setLoading] = useState(!hasPreload);
  const [error, setError] = useState<string | null>(null);

  const meta = MODULES_BY_KEY[moduleKey];
  const displayName = language === "ar" ? meta?.name_ar : meta?.name_en;
  const description = meta?.description || "";

  // Keep `data` in sync when the parent's preloaded slice changes (e.g. job
  // polled and produced fresh results). Avoid hitting the network at all in
  // the preloaded code path — that's the whole point of Area 2.
  useEffect(() => {
    if (hasPreload) {
      setData(preloadedData);
      setLoading(false);
      setError(null);
    }
  }, [hasPreload, preloadedData]);

  useEffect(() => {
    if (hasPreload) return;     // Parent owns the fetch — bail out here.
    if (!jobId) {
      setLoading(false);
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);

    analyticsApi
      .summary(jobId)
      .then((res) => {
        if (cancelled) return;
        const modules = res.data?.modules || {};
        setData(modules[moduleKey] ?? null);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e?.response?.data?.detail || e?.message || "Failed to load data");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [hasPreload, jobId, moduleKey]);

  const ChartComponent = chartRegistry[moduleKey];

  const isRenderable = (() => {
    if (!data || typeof data !== "object") return false;
    const keys = Object.keys(data).filter((k) => k !== "warning" && k !== "summary");
    return keys.some((k) => {
      const v = (data as any)[k];
      if (Array.isArray(v)) return v.length > 0;
      if (v && typeof v === "object") return Object.keys(v).length > 0;
      return v != null;
    }) || (data.summary && Object.keys(data.summary).length > 0);
  })();

  const fallbackTitle = displayName || moduleKey;

  return (
    <div ref={cardRef} className="w-full h-full relative group">
      {/* Before the card scrolls into view, show a lightweight skeleton to
          keep the DOM cheap and prevent layout jank from 39 simultaneous
          chart renders on page load. */}
      {!isVisible ? (
        <InsightCard title={fallbackTitle}>
          <ChartSkeleton />
        </InsightCard>
      ) : (
        <>
          {/* Kebab → Export CSV / JSON. Always visible (hover-revealed) so
              users can grab the underlying data without going to Customize Mode. */}
          {!loading && !error && isRenderable && (
            <ChartExportMenu data={data} moduleKey={moduleKey} />
          )}

          {isCustomizing && (
            <button
              type="button"
              onClick={() => removeWidget(widgetId)}
              className="no-drag absolute top-2 right-10 z-50 p-1.5 bg-rose-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-rose-600 shadow-md"
              aria-label="Remove widget"
            >
              <X className="w-4 h-4" />
            </button>
          )}

          {loading && (
            <InsightCard title={fallbackTitle}>
              <ChartSkeleton />
            </InsightCard>
          )}

          {!loading && error && (
            <InsightCard title={fallbackTitle}>
              <ErrorEmpty message={error} />
            </InsightCard>
          )}

          {!loading && !error && !isRenderable && (
            <InsightCard title={fallbackTitle}>
              <NoDataEmpty description={description || "This chart has no data for the current job."} />
            </InsightCard>
          )}

          {!loading && !error && isRenderable && (
            ChartComponent ? (
              <ChartComponent data={data} moduleKey={moduleKey} />
            ) : (
              <InsightCard title={fallbackTitle}>
                <NoDataEmpty description="Chart component not registered yet." />
              </InsightCard>
            )
          )}
        </>
      )}
    </div>
  );
}

// memo prevents all 39 cards re-rendering on parent re-renders (layout moves,
// store updates). Each card only re-renders when its own props change.
export const ChartCard = memo(ChartCardInner);
