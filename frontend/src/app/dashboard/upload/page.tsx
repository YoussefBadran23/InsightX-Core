'use client';

import { useState, useRef } from 'react';
import { UploadCloud, File, X, CheckCircle, AlertCircle, Play, Loader2 } from 'lucide-react';
import { uploadApi } from '@/lib/api';
import { useJobStore } from '@/stores/jobStore';
import { useUiStore } from '@/stores/uiStore';
import { t } from '@/lib/i18n';
import { useRouter } from 'next/navigation';

type Stage = 'idle' | 'sniffing' | 'confirming' | 'done';

export default function UploadPage() {
  const language = useUiStore((s) => s.language);
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [stage, setStage] = useState<Stage>('idle');
  const [error, setError] = useState('');
  const [statusText, setStatusText] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const { startPolling } = useJobStore();
  const router = useRouter();

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return;
    setError('');

    // ── Step 1: sniff (auto-detect column mappings) ──
    setStage('sniffing');
    setStatusText(t('upload_readingStatus', language));
    let sniffData: { sniff_id: string; mappings: any[] };
    try {
      const sniffRes = await uploadApi.sniffCsv(file);
      sniffData = sniffRes.data as { sniff_id: string; mappings: any[] };
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to read file.');
      setStage('idle');
      return;
    }

    // ── Step 2: auto-confirm the AI's suggested mappings ──
    setStage('confirming');
    setStatusText(t('upload_startingStatus', language));
    try {
      const confirmRes = await uploadApi.confirmMappings({
        sniff_id: sniffData.sniff_id,
        confirmed_mappings: sniffData.mappings.map((m) => ({
          csv_header: m.csv_header,
          internal_column: m.internal_column,
        })),
      });
      const jobId = (confirmRes.data as any).job_id as string;
      // Kick polling and route to the analytics page where the user can watch progress.
      startPolling(jobId);
      setStage('done');
      router.push('/dashboard/analytics');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to start analysis.');
      setStage('idle');
    }
  };

  const busy = stage === 'sniffing' || stage === 'confirming';

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 animate-fade-in flex flex-col items-center justify-center">
      <div className="w-full max-w-2xl flex flex-col gap-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-2">{t('upload_title', language)}</h1>
          <p className="text-slate-500 dark:text-slate-400">{t('upload_subtitle', language)}</p>
        </div>

        <div className="bg-white dark:bg-surface-elevated rounded-xl shadow-sm border border-gray-200 dark:border-surface-border p-8">
          {error && (
            <div className="mb-6 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-600 dark:text-red-400 text-sm p-4 rounded-lg flex items-center gap-2">
              <AlertCircle className="w-5 h-5 shrink-0" />
              {error}
            </div>
          )}

          <div
            className={`relative flex flex-col items-center justify-center w-full h-64 border-2 border-dashed rounded-xl transition-colors ${
              dragActive
                ? 'border-primary bg-primary/5'
                : 'border-gray-300 dark:border-surface-border bg-gray-50 dark:bg-background-dark/50 hover:bg-gray-100 dark:hover:bg-surface-border/50'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv"
              onChange={handleChange}
              disabled={busy}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
            />

            <div className="flex flex-col items-center justify-center pt-5 pb-6 pointer-events-none">
              <UploadCloud className={`w-12 h-12 mb-4 ${dragActive ? 'text-primary' : 'text-slate-400'}`} />
              <p className="mb-2 text-sm text-slate-500 dark:text-slate-400">
                <span className="font-bold text-primary">{t('upload_dropHere', language)}</span> {t('upload_or', language)}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-500">{t('upload_csvOnly', language)}</p>
            </div>
          </div>

          {file && (
            <div className="mt-6 flex items-center justify-between p-4 bg-gray-50 dark:bg-background-dark rounded-lg border border-gray-200 dark:border-surface-border">
              <div className="flex items-center gap-3 overflow-hidden">
                <File className="w-8 h-8 text-primary shrink-0" />
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-medium text-gray-900 dark:text-white truncate">{file.name}</span>
                  <span className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                </div>
              </div>
              <button
                onClick={() => setFile(null)}
                className="p-2 text-slate-400 hover:text-red-500 transition-colors disabled:opacity-50"
                disabled={busy}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          )}

          {busy && (
            <div className="mt-4 flex items-center gap-3 text-sm text-slate-600 dark:text-slate-300">
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
              {statusText}
            </div>
          )}

          <div className="mt-8 pt-6 border-t border-gray-200 dark:border-surface-border flex justify-end">
            <button
              onClick={handleUpload}
              disabled={!file || busy}
              className="flex items-center gap-2 bg-primary hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 px-6 rounded-lg shadow-lg shadow-primary/20 transition-all"
            >
              {busy ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  {stage === 'sniffing' ? t('upload_reading', language) : t('upload_starting', language)}
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" fill="currentColor" />
                  {t('upload_btn', language)}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Feature highlights */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-4">
          <div className="flex flex-col items-center text-center p-4">
            <CheckCircle className="w-8 h-8 text-emerald-500 mb-3" />
            <h3 className="font-bold text-gray-900 dark:text-white text-sm">{t('upload_featCleaning', language)}</h3>
            <p className="text-xs text-slate-500 mt-1">{t('upload_featCleaningDesc', language)}</p>
          </div>
          <div className="flex flex-col items-center text-center p-4">
            <CheckCircle className="w-8 h-8 text-purple-500 mb-3" />
            <h3 className="font-bold text-gray-900 dark:text-white text-sm">{t('upload_featModules', language)}</h3>
            <p className="text-xs text-slate-500 mt-1">{t('upload_featModulesDesc', language)}</p>
          </div>
          <div className="flex flex-col items-center text-center p-4">
            <CheckCircle className="w-8 h-8 text-blue-500 mb-3" />
            <h3 className="font-bold text-gray-900 dark:text-white text-sm">{t('upload_featDashboard', language)}</h3>
            <p className="text-xs text-slate-500 mt-1">{t('upload_featDashboardDesc', language)}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
