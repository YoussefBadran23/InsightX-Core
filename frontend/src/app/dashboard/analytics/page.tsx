'use client';

import { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, Clock, Loader2, MinusCircle, AlertCircle, FileText } from 'lucide-react';
import { jobsApi, analyticsApi } from '@/lib/api';
import { useUiStore } from '@/stores/uiStore';
import { t } from '@/lib/i18n';
import type { ModuleStatus, UploadJob } from '@/types';

interface JobWithModules extends UploadJob {
  modules?: ModuleStatus[];
}

// `label` is resolved against the current locale inside the component so this
// stays a pure visual config — colors / icons only.
const STATUS_META: Record<
  ModuleStatus['run_status'],
  { labelKey: 'analytics_status_completed' | 'analytics_status_running' | 'analytics_status_pending' | 'analytics_status_failed' | 'analytics_status_skipped'; cls: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  completed: { labelKey: 'analytics_status_completed', cls: 'text-emerald-600 dark:text-emerald-500 bg-emerald-100 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/30', Icon: CheckCircle2 },
  failed:    { labelKey: 'analytics_status_failed',    cls: 'text-red-600 dark:text-red-500 bg-red-100 dark:bg-red-500/10 border-red-200 dark:border-red-500/30',                Icon: XCircle },
  running:   { labelKey: 'analytics_status_running',   cls: 'text-blue-600 dark:text-blue-500 bg-blue-100 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/30',            Icon: Loader2 },
  pending:   { labelKey: 'analytics_status_pending',   cls: 'text-amber-600 dark:text-amber-500 bg-amber-100 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/30',     Icon: Clock },
  skipped:   { labelKey: 'analytics_status_skipped',   cls: 'text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-500/10 border-slate-200 dark:border-slate-500/30',     Icon: MinusCircle },
};

export default function AnalyticsPage() {
  const language = useUiStore((s) => s.language);
  const [job, setJob] = useState<JobWithModules | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        // 1. Get latest job
        const jobsRes = await jobsApi.list(1, 1);
        const latest = (jobsRes.data?.items?.[0] || null) as UploadJob | null;
        if (!latest) {
          if (!cancelled) {
            setError(t('analytics_noJobs', language));
            setLoading(false);
          }
          return;
        }

        // 2. Get its modules
        const modulesRes = await jobsApi.getModules(latest.id);
        if (cancelled) return;
        setJob({ ...latest, modules: modulesRes.data as ModuleStatus[] });

        // 3. Get analytics summary (all module result JSONs in one shot)
        try {
          const sumRes = await analyticsApi.summary(latest.id);
          if (!cancelled) setSummary(sumRes.data?.modules || null);
        } catch {
          /* non-fatal */
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.response?.data?.detail || e?.message || 'Failed to load analytics');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();

    // Re-poll every 3s while job is still processing.
    const interval = setInterval(() => {
      if (job && (job.status === 'completed' || job.status === 'completed_with_errors' || job.status === 'failed')) return;
      load();
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading && !job) {
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

  const modules = job?.modules || [];
  const counts = modules.reduce(
    (acc, m) => {
      acc[m.run_status] = (acc[m.run_status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8">
      <div className="mx-auto max-w-6xl flex flex-col gap-6 animate-fade-in">
        {/* Header */}
        <div className="flex flex-col gap-1">
          <h1 className="text-gray-900 dark:text-white text-3xl font-black tracking-tight">{t('analytics_title', language)}</h1>
          <p className="text-slate-500 dark:text-slate-400">
            {t('analytics_jobId', language)}{' '}
            <span className="font-mono text-xs bg-gray-100 dark:bg-surface-elevated px-1.5 py-0.5 rounded">
              {job?.id?.slice(0, 8)}
            </span>{' '}
            · {t('analytics_status', language)}{' '}
            <span className="font-medium text-gray-900 dark:text-white">{job?.status}</span> ·{' '}
            {job?.rows_processed?.toLocaleString() || 0} {t('analytics_rowsProcessed', language)}
          </p>
        </div>

        {/* Status summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {(['completed', 'running', 'pending', 'failed', 'skipped'] as const).map((s) => {
            const m = STATUS_META[s];
            const n = counts[s] || 0;
            return (
              <div key={s} className={`rounded-xl border ${m.cls} p-4 flex items-center gap-3`}>
                <m.Icon className={`w-5 h-5 ${s === 'running' ? 'animate-spin' : ''}`} />
                <div>
                  <p className="text-xs uppercase tracking-wider opacity-80">{t(m.labelKey, language)}</p>
                  <p className="text-2xl font-bold leading-none mt-1">{n}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Module list */}
        <div className="bg-white dark:bg-surface-elevated rounded-xl border border-gray-200 dark:border-surface-border overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-surface-border">
            <h2 className="text-gray-900 dark:text-white text-lg font-bold">
              {t('analytics_modules', language)} ({modules.length})
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-sm">
              {t('analytics_modulesDesc', language)}
            </p>
          </div>

          <ul className="divide-y divide-gray-200 dark:divide-surface-border">
            {modules.length === 0 && (
              <li className="px-6 py-8 text-center text-slate-500">{t('analytics_noModules', language)}</li>
            )}
            {modules.map((m) => {
              const meta = STATUS_META[m.run_status] || STATUS_META.pending;
              const cached = summary?.[m.module_key];
              const cachedKeys = cached && typeof cached === 'object' ? Object.keys(cached) : [];
              return (
                <li key={m.module_key} className="px-6 py-4 hover:bg-gray-50 dark:hover:bg-surface-border/30 transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <meta.Icon className={`w-5 h-5 mt-0.5 ${meta.cls.split(' ')[0]} ${m.run_status === 'running' ? 'animate-spin' : ''}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs bg-gray-100 dark:bg-background-dark px-1.5 py-0.5 rounded text-slate-600 dark:text-slate-400">
                            {m.module_key}
                          </span>
                          <span className="text-gray-900 dark:text-white font-medium">{m.module_name}</span>
                          <span dir="rtl" className="text-slate-500 text-sm">{m.module_name_ar}</span>
                        </div>
                        <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">{m.description}</p>

                        {m.run_status === 'skipped' && m.missing_required_columns && m.missing_required_columns.length > 0 && (
                          <p className="text-amber-600 dark:text-amber-400 text-xs mt-2">
                            {t('analytics_missingRequired', language)}: {m.missing_required_columns.join(', ')}
                          </p>
                        )}

                        {m.error_message && m.run_status !== 'completed' && (
                          <p className="text-red-600 dark:text-red-400 text-xs mt-2 font-mono">
                            {m.error_message}
                          </p>
                        )}

                        {m.run_status === 'completed' && cachedKeys.length > 0 && (
                          <div className="flex items-center gap-2 mt-2 flex-wrap">
                            <FileText className="w-3.5 h-3.5 text-slate-400" />
                            <span className="text-xs text-slate-500">{t('analytics_resultSections', language)}:</span>
                            {cachedKeys.slice(0, 6).map((k) => (
                              <span
                                key={k}
                                className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-background-dark text-slate-600 dark:text-slate-300 rounded font-mono"
                              >
                                {k}
                              </span>
                            ))}
                            {cachedKeys.length > 6 && (
                              <span className="text-xs text-slate-400">+{cachedKeys.length - 6} {t('analytics_more', language)}</span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    <span
                      className={`shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${meta.cls}`}
                    >
                      {t(meta.labelKey, language)}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
