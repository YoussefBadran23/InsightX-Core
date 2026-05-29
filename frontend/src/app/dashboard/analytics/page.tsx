'use client';

/**
 * Analytics page.
 *
 * Renders a single customizable chart dashboard. The page is intentionally
 * minimal — its only chrome is the title and the "Customize Dashboard"
 * toggle. Everything else lives inside `<CustomizableDashboard>`.
 *
 * The previous design surfaced job status counts and a long "Modules (39)"
 * list. Both were removed per user request — the charts themselves convey
 * the analytics state more directly.
 */

import { useEffect, useRef, useState } from 'react';
import { Loader2, AlertCircle, LayoutDashboard, Save, RotateCcw, X as XIcon, ChevronRight, FileSpreadsheet, FileText } from 'lucide-react';

import { jobsApi, analyticsApi } from '@/lib/api';
import { useUiStore } from '@/stores/uiStore';
import { useDashboardStore } from '@/stores/dashboardStore';
import { t } from '@/lib/i18n';
import type { UploadJob } from '@/types';

import { ModuleSidebar } from '@/components/dashboard/ModuleSidebar';
import { CustomizableDashboard } from '@/components/dashboard/CustomizableDashboard';
import { exportAnalyticsToExcel, exportElementToPdf } from '@/lib/dashboardExport';

export default function AnalyticsPage() {
  const language = useUiStore((s) => s.language);
  const isCustomizing = useDashboardStore((s) => s.isCustomizing);
  const toggleCustomizing = useDashboardStore((s) => s.toggleCustomizing);
  const initialized = useDashboardStore((s) => s.initialized);
  const seedDefaultDashboard = useDashboardStore((s) => s.seedDefaultDashboard);
  const saveLayout = useDashboardStore((s) => s.saveLayout);
  const cancelLayout = useDashboardStore((s) => s.cancelLayout);
  const resetLayout = useDashboardStore((s) => s.resetLayout);

  const [job, setJob] = useState<UploadJob | null>(null);
  // Ref mirrors `job` state so the setInterval callback always reads the
  // current value without becoming stale (closures capture the initial null).
  const jobRef = useRef<UploadJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Single-fetch analytics state. Holds the full {module_key → result_json}
  // dict so every <ChartCard> renders from this one source instead of
  // firing its own /analytics/summary call. `undefined` here means
  // "fetch hasn't run yet" — components still spin a loading state.
  const [analyticsModules, setAnalyticsModules] = useState<Record<string, unknown> | null | undefined>(undefined);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  // Export state — disables buttons while a snapshot is rendering so the
  // user doesn't click twice and end up with two PDFs.
  const [exportingExcel, setExportingExcel] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const gridRef = useRef<HTMLDivElement>(null);

  // First-visit seeding: fill the grid with every module from the catalog
  // so users see all 39 charts immediately. Persisted via `initialized`
  // flag so we never re-seed if the user later empties their layout.
  useEffect(() => {
    if (!initialized) seedDefaultDashboard();
  }, [initialized, seedDefaultDashboard]);

  // ── DnD note ──────────────────────────────────────────────────────────
  //   Drag-and-drop runs through react-grid-layout's native HTML5 drop
  //   API now (see ModuleSidebar + CustomizableDashboard). No @dnd-kit
  //   context to wire up here — sidebar items are native draggables and
  //   the grid is the native drop target. Removing the dnd-kit layer is
  //   what lets the cursor position propagate to RGL's onDrop callback,
  //   so widgets land where the user releases instead of always at the
  //   end of the layout. ──────────────────────────────────────────────────

  // ── Export handlers ───────────────────────────────────────────────────
  //   Excel: builds one workbook from the pre-fetched analyticsModules dict
  //     — Summary sheet + one sheet per module's primary array (by_channel,
  //     top_customers, etc.).
  //   PDF: html2canvas-snapshots whichever DOM region the user is looking
  //     at (the dashboard grid) and writes a single-page PDF sized to fit.
  const handleExportExcel = async () => {
    if (!analyticsModules || exportingExcel) return;
    setExportingExcel(true);
    try {
      await exportAnalyticsToExcel(analyticsModules as Record<string, unknown>);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Excel export failed:', e);
    } finally {
      setExportingExcel(false);
    }
  };

  const handleExportPdf = async () => {
    if (!gridRef.current || exportingPdf) return;
    setExportingPdf(true);
    try {
      await exportElementToPdf(gridRef.current);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('PDF export failed:', e);
    } finally {
      setExportingPdf(false);
    }
  };

  // ── Latest-job lookup. We only need the job's id (charts use it to fetch
  //    their own data). If the job is still running we keep polling so a
  //    fresh upload's results land on the page without a manual refresh.
  //
  //    jobRef mirrors `job` state so the setInterval callback always reads
  //    the *current* value — a plain closure over `job` would capture the
  //    initial null and poll forever even after the job completes. ──
  useEffect(() => {
    let cancelled = false;
    async function loadLatestJob() {
      try {
        const res = await jobsApi.list(1, 1);
        const latest = (res.data?.items?.[0] || null) as UploadJob | null;
        if (cancelled) return;
        if (!latest) {
          setError(t('analytics_noJobs', language));
          setLoading(false);
          return;
        }
        jobRef.current = latest;   // keep ref in sync for the interval
        setJob(latest);
        setError(null);
        setLoading(false);
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.response?.data?.detail || e?.message || 'Failed to load analytics');
        setLoading(false);
      }
    }
    loadLatestJob();

    const interval = setInterval(() => {
      // Read from the ref, not the stale closure variable.
      const current = jobRef.current;
      if (current && (current.status === 'completed' || current.status === 'failed')) {
        clearInterval(interval);   // stop as soon as job is terminal
        return;
      }
      loadLatestJob();
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Single-fetch analytics. Pulls /analytics/summary ONCE for the entire
  //    grid (vs the old N+1 design where every chart-card fetched the same
  //    payload independently — 39 round-trips on the analytics page alone).
  //    Refetches only when the job's terminal state flips, so an in-progress
  //    upload still surfaces new results when it completes.
  useEffect(() => {
    if (!job?.id) return;
    let cancelled = false;
    setAnalyticsError(null);
    analyticsApi
      .summary(job.id)
      .then((res) => {
        if (cancelled) return;
        setAnalyticsModules((res.data?.modules || {}) as Record<string, unknown>);
      })
      .catch((e: any) => {
        if (cancelled) return;
        setAnalyticsError(
          e?.response?.data?.detail || e?.message || 'Failed to load analytics summary',
        );
        // Surface an empty dict on error so the grid still renders cards
        // (each will fall back to its own per-card fetch).
        setAnalyticsModules(null);
      });
    return () => {
      cancelled = true;
    };
  }, [job?.id, job?.status]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 flex items-center justify-center h-full">
        <div className="max-w-md text-center">
          <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-300">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <ModuleSidebar open={isCustomizing} onClose={cancelLayout} />

      {/* ── Customize-mode top bar ────────────────────────────────────────
          When `isCustomizing` is on, replace the page chrome with the
          breadcrumb + EDITING badge + Reset / Cancel / Save Layout buttons
          described in the spec. Rendered as a sticky sub-header inside the
          analytics page so the side nav remains visible (matches our other
          dashboard pages — the sub-header sits below the global header). */}
      {isCustomizing && (
        <div className="sticky top-0 z-20 h-14 border-b border-gray-200 dark:border-surface-border bg-white/95 dark:bg-surface-card/95 backdrop-blur flex items-center justify-between px-6">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400 font-medium">
              {language === 'ar' ? 'لوحة التحكم' : 'Dashboard'}
            </span>
            <ChevronRight className="w-4 h-4 text-slate-400" />
            <span className="text-gray-900 dark:text-white font-medium">
              {language === 'ar' ? 'وضع التخصيص' : 'Customization Mode'}
            </span>
            <span className="ms-2 px-2 py-0.5 rounded-full bg-primary/10 dark:bg-primary/20 text-primary text-[10px] font-bold border border-primary/20 dark:border-primary/30 animate-pulse uppercase tracking-wider">
              {language === 'ar' ? 'تحرير' : 'Editing'}
            </span>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={resetLayout}
              className="flex items-center gap-1.5 h-9 px-3 rounded-lg border border-gray-300 dark:border-surface-border text-gray-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white hover:border-gray-400 dark:hover:border-white transition-all text-xs font-bold active:scale-95"
              title={language === 'ar' ? 'إعادة إلى الافتراضي' : 'Reset to default layout'}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{language === 'ar' ? 'إعادة' : 'Reset'}</span>
            </button>
            <button
              type="button"
              onClick={cancelLayout}
              className="flex items-center gap-1.5 h-9 px-3 rounded-lg bg-gray-200 dark:bg-surface-elevated text-gray-700 dark:text-white hover:bg-gray-300 dark:hover:bg-surface-elevated/80 transition-all text-xs font-bold active:scale-95"
            >
              <XIcon className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{language === 'ar' ? 'إلغاء' : 'Cancel'}</span>
            </button>
            <button
              type="button"
              onClick={saveLayout}
              className="flex items-center gap-1.5 h-9 px-4 rounded-lg bg-primary hover:bg-primary-hover text-white shadow-lg shadow-primary/30 transition-all text-xs font-bold active:scale-95"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{language === 'ar' ? 'حفظ التخطيط' : 'Save Layout'}</span>
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-6 md:p-8 bg-grid-pattern-soft">
        <div className="mx-auto max-w-7xl flex flex-col gap-6 animate-fade-in">
          {/* Header — title + Customize toggle. Job metadata, status
              counters, and module list were intentionally removed; the
              charts themselves carry that information. */}
          {!isCustomizing && (
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <h1 className="text-gray-900 dark:text-white text-3xl font-black tracking-tight">
                {t('analytics_title', language)}
              </h1>

              <div className="flex items-center gap-2 shrink-0">
                {/* Excel + PDF export. Disabled while a job is still
                    running or a render is in flight. */}
                <button
                  type="button"
                  onClick={handleExportExcel}
                  disabled={!analyticsModules || exportingExcel}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold border border-gray-300 dark:border-surface-border text-gray-700 dark:text-slate-200 hover:bg-gray-50 dark:hover:bg-surface-elevated disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
                  title={language === 'ar' ? 'تصدير إلى Excel' : 'Export to Excel (.xlsx)'}
                >
                  {exportingExcel
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />}
                  <span className="hidden sm:inline">
                    {language === 'ar' ? 'Excel' : 'Excel'}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={handleExportPdf}
                  disabled={!analyticsModules || exportingPdf}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold border border-gray-300 dark:border-surface-border text-gray-700 dark:text-slate-200 hover:bg-gray-50 dark:hover:bg-surface-elevated disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
                  title={language === 'ar' ? 'تصدير إلى PDF' : 'Export to PDF'}
                >
                  {exportingPdf
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <FileText className="w-3.5 h-3.5 text-rose-500" />}
                  <span className="hidden sm:inline">PDF</span>
                </button>

                <button
                  type="button"
                  onClick={toggleCustomizing}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors shrink-0 bg-primary border-primary text-white hover:bg-primary-hover"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  {language === 'ar' ? 'تخصيص لوحة التحكم' : 'Customize Dashboard'}
                </button>
              </div>
            </div>
          )}

          {/* Customizable chart dashboard — populated with all 39 charts on
              first visit; user can rearrange / remove via Customize mode.
              `analyticsModules` is the single-fetch result; each ChartCard
              reads its slice instead of issuing its own GET.

              The wrapping div is the html2canvas snapshot target for the
              PDF-export button — wrapping at this level captures the entire
              grid (and only the grid) without page chrome. */}
          <div ref={gridRef}>
            <CustomizableDashboard
              jobId={job?.id || null}
              analyticsModules={analyticsModules}
            />
          </div>
          {analyticsError && (
            <div className="text-[11px] text-amber-600 dark:text-amber-400 -mt-2 ms-1">
              {analyticsError} · cards will fall back to per-widget fetch.
            </div>
          )}
        </div>
      </div>

      {/* Drag overlay note: native HTML5 DnD uses the browser's own ghost
          (a faded copy of the source element) — no React overlay portal
          required. The previous DragOverlay re-implemented this with @dnd-kit
          but introduced a separate DnD context that didn't talk to RGL. */}
    </>
  );
}
