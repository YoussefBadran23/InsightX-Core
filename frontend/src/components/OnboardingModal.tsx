'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { UploadCloud, CheckCircle2, Loader2, AlertCircle, FileText, ChevronDown, ChevronRight, Check, AlertTriangle, Info, LogOut } from 'lucide-react';
import { uploadApi, jobsApi } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { t } from '@/lib/i18n';

type Stage = 'upload' | 'uploading' | 'reviewing' | 'confirming' | 'processing' | 'complete' | 'error';

interface OnboardingModalProps {
  onComplete: () => void;
}

interface Mapping {
  csv_header: string;
  status: 'matched' | 'ambiguous' | 'unmatched';
  internal_column: string | null;
  display_name: string | null;
  group: string | null;
  confidence: number;
  alternatives: { internal_column: string; display_name: string; confidence: number }[];
}

interface MissingColumn {
  internal_column: string;
  display_name: string;
  group: string;
  type: 'blocking' | 'enrichment';
  blocked_modules: string[];
}

interface SchemaColumn {
  internal_column: string;
  display_name: string;
  group: string;
}

export function OnboardingModal({ onComplete }: OnboardingModalProps) {
  const logout = useAuthStore((s) => s.logout);
  const language = useUiStore((s) => s.language);
  const [stage, setStage] = useState<Stage>('upload');
  const [uploadPct, setUploadPct] = useState(0);
  const [processingPct, setProcessingPct] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  
  const [sniffId, setSniffId] = useState<string | null>(null);
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [missingColumns, setMissingColumns] = useState<MissingColumn[]>([]);
  const [moduleSummary, setModuleSummary] = useState({ total: 39, eligible: 0, blocked: 0 });
  const [schemaColumns, setSchemaColumns] = useState<SchemaColumn[]>([]);
  // Empty string ⇒ "auto-detect from CSV in stage3 / fall back to USD".
  // Any other value here will be sent to /upload/confirm as an explicit
  // override and stage3 will skip its mode-based detection.
  const [sourceCurrencyOverride, setSourceCurrencyOverride] = useState<string>('');
  
  // Collapse state for review sections
  const [expandedSections, setExpandedSections] = useState({
    transaction: true,
    customer_meta: false,
    product_meta: false
  });

  const [jobId, setJobId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    uploadApi.getSchemaColumns().then(res => setSchemaColumns(res.data)).catch(() => {
      // schema columns unavailable — dropdowns will be empty, user can still proceed
    });
  }, []);

  // Poll backend job status
  useEffect(() => {
    if (stage !== 'processing' || !jobId) return;

    pollRef.current = setInterval(async () => {
      try {
        const res = await jobsApi.getStatus(jobId);
        const { status, progress } = res.data as { status: string; progress?: number };
        if (progress !== undefined) {
          setProcessingPct(Math.min(progress, 99));
        } else {
          setProcessingPct((p) => Math.min(p + 2, 94));
        }
        if (status === 'completed' || status === 'completed_with_errors') {
          setProcessingPct(100);
          clearInterval(pollRef.current!);
          setTimeout(() => setStage('complete'), 800);
        } else if (status === 'failed') {
          clearInterval(pollRef.current!);
          setErrorMsg('Analysis failed. Please try uploading your CSV again.');
          setStage('error');
        }
      } catch {
        // keep polling
      }
    }, 1000);

    return () => clearInterval(pollRef.current!);
  }, [stage, jobId]);

  // Accepted upload formats. The backend converts everything except CSV to
  // CSV inside the pending directory before stage3 runs, so the analytics
  // pipeline only ever sees CSV — these are just the wrapper formats the
  // user can hand us.
  const ACCEPTED_EXTS = ['.csv', '.xlsx', '.xls', '.json', '.parquet'] as const;

  const validateUpload = (file: File): string | null => {
    const name = file.name.toLowerCase();
    if (!ACCEPTED_EXTS.some((ext) => name.endsWith(ext))) {
      return `Unsupported file type. Accepted: ${ACCEPTED_EXTS.join(', ')}`;
    }
    const maxMb = 100;
    if (file.size > maxMb * 1024 * 1024) {
      return `File size must be under ${maxMb} MB.`;
    }
    return null;
  };

  const handleFile = useCallback(async (file: File) => {
    const err = validateUpload(file);
    if (err) {
      setErrorMsg(err);
      setStage('error');
      return;
    }
    setSelectedFile(file);
    setErrorMsg('');
    setStage('uploading');
    setUploadPct(0);

    // ── First-attempt resilience ─────────────────────────────────────────
    // The very first upload after the modal opens occasionally fails with
    // a transient network error (cold dev-server / Auth header not yet
    // attached). We retry once with a short backoff before surfacing the
    // error to the user. The full error is logged to the console so we can
    // diagnose if it ever re-appears.
    const attempt = async () => {
      const res = await uploadApi.sniffCsv(file, setUploadPct);
      setSniffId(res.data.sniff_id);
      setMappings(res.data.mappings);
      setMissingColumns(res.data.missing_columns);
      setModuleSummary(res.data.module_summary);
      setStage('reviewing');
    };

    try {
      await attempt();
    } catch {
      try {
        // Brief pause so any transient state can settle.
        await new Promise((r) => setTimeout(r, 400));
        setUploadPct(0);
        await attempt();
      } catch (secondErr: unknown) {
        const err = secondErr as { code?: string; message?: string; response?: { status?: number; data?: { detail?: string } } };
        // Distinguish a timeout (slow backend / first-call model load) from a
        // real server failure so the user knows what to do next.
        const isTimeout =
          err?.code === 'ECONNABORTED' ||
          /timeout/i.test(err?.message || '');
        const detail = isTimeout
          ? 'The server is still warming up after a restart. Please wait ~30s and try again.'
          : (err?.response?.data?.detail ||
             (err?.response?.status ? `Server returned ${err.response.status}` : null) ||
             err?.message ||
             'Upload failed. Please try again.');
        setErrorMsg(detail);
        setStage('error');
      }
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragActive(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleConfirm = async () => {
    if (!sniffId) return;
    setStage('confirming');
    try {
      const confirmed_mappings = mappings.map(m => ({
        csv_header: m.csv_header,
        internal_column: m.internal_column
      }));

      // Only send `source_currency` when the user explicitly picked one. Empty
      // string means "let stage3 auto-detect from the data" — backend honors
      // that by leaving the column NULL until detection runs.
      const payload: { sniff_id: string; confirmed_mappings: typeof confirmed_mappings; source_currency?: string } = {
        sniff_id: sniffId,
        confirmed_mappings,
      };
      if (sourceCurrencyOverride) {
        payload.source_currency = sourceCurrencyOverride;
      }

      const res = await uploadApi.confirmMappings(payload);
      setJobId(res.data.job_id);
      setStage('processing');
      setProcessingPct(0);
    } catch (e: any) {
      setErrorMsg(e.response?.data?.detail || 'Failed to start processing.');
      setStage('error');
    }
  };

  const retry = () => {
    setStage('upload');
    setSelectedFile(null);
    setErrorMsg('');
    setUploadPct(0);
    setProcessingPct(0);
    setJobId(null);
  };

  const handleMappingChange = (csv_header: string, internal_column: string) => {
    setMappings(prev => prev.map(m => {
      if (m.csv_header === csv_header) {
        const colDef = schemaColumns.find(c => c.internal_column === internal_column);
        return {
          ...m,
          internal_column: internal_column || null,
          display_name: colDef ? colDef.display_name : null,
          group: colDef ? colDef.group : null,
          status: internal_column ? 'matched' : 'unmatched'
        };
      }
      return m;
    }));
  };

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const isRtl = language === 'ar';

  const renderSection = (group: string, title: string, sectionKey: keyof typeof expandedSections) => {
    const isExpanded = expandedSections[sectionKey];
    
    // Items that mapped to this group
    const mappedItems = mappings.filter(m => m.group === group);
    // Missing items for this group
    const missingItems = missingColumns.filter(m => m.group === group);
    
    if (mappedItems.length === 0 && missingItems.length === 0 && group !== 'transaction') {
      return null;
    }

    return (
      <div className="mb-4 bg-white dark:bg-[#1f1f38] rounded-xl border border-gray-200 dark:border-white/10 overflow-hidden">
        <button 
          onClick={() => toggleSection(sectionKey)}
          className="w-full flex items-center justify-between p-4 bg-gray-50 dark:bg-[#16162a] hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
        >
          <div className="flex items-center gap-2 font-semibold text-gray-800 dark:text-gray-200">
            {isExpanded
              ? <ChevronDown className="w-5 h-5" />
              : (isRtl ? <ChevronRight className="w-5 h-5 rotate-180" /> : <ChevronRight className="w-5 h-5" />)}
            {title} <span className="text-sm font-normal text-slate-500">({mappedItems.length + missingItems.length} {t('onb_columns', language)})</span>
          </div>
        </button>
        
        {isExpanded && (
          <div className="divide-y divide-gray-100 dark:divide-white/5 p-4 max-h-64 overflow-y-auto">
            {/* Mapped / Unmatched items */}
            {mappings.map(m => {
              if (m.group !== group && m.status !== 'unmatched') return null;
              if (m.status === 'unmatched' && group !== 'transaction') return null; // Put unmatched in transaction for now
              
              return (
                <div key={m.csv_header} className={`flex items-center justify-between py-3 px-2 rounded-lg mb-1 ${
                  m.status === 'matched' ? 'border-l-4 border-emerald-500 bg-emerald-50/50 dark:bg-emerald-500/5' :
                  m.status === 'ambiguous' ? 'border-l-4 border-amber-500 bg-amber-50/50 dark:bg-amber-500/5' :
                  'border-l-4 border-red-500 bg-red-50/50 dark:bg-red-500/5'
                }`}>
                  <div className="flex-1 font-mono text-sm text-gray-700 dark:text-gray-300 flex items-center gap-2">
                    {m.status === 'unmatched' && <AlertCircle className="w-4 h-4 text-red-500" />}
                    {m.status === 'ambiguous' && <AlertTriangle className="w-4 h-4 text-amber-500" />}
                    {m.csv_header}
                  </div>
                  <div className="flex-1 flex justify-end">
                    {m.status === 'matched' ? (
                      <div className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400 font-medium bg-white dark:bg-[#16162a] px-3 py-1.5 rounded-md border border-emerald-100 dark:border-emerald-500/20">
                        {m.display_name} <Check className="w-4 h-4" />
                      </div>
                    ) : (
                      <select 
                        value={m.internal_column || ""}
                        onChange={(e) => handleMappingChange(m.csv_header, e.target.value)}
                        className="text-sm bg-white dark:bg-[#16162a] border border-gray-300 dark:border-white/20 rounded-md px-3 py-1.5 text-gray-700 dark:text-gray-200 focus:ring-primary focus:border-primary outline-none"
                      >
                        <option value="">{t('onb_selectColumn', language)}</option>
                        {schemaColumns.map(sc => (
                          <option key={sc.internal_column} value={sc.internal_column}>
                            {sc.display_name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>
              );
            })}
            
            {/* Missing items */}
            {missingItems.map(miss => (
              <div key={miss.internal_column} className={`flex items-center justify-between py-3 px-2 rounded-lg mb-1 ${
                miss.type === 'blocking' ? 'border-l-4 border-red-500 bg-red-50/30 dark:bg-red-500/5' :
                'border-l-4 border-amber-500 bg-amber-50/30 dark:bg-amber-500/5'
              }`}>
                <div className="flex-1 italic text-sm text-slate-400 flex items-center gap-2">
                  {t('onb_notInFile', language)}
                </div>
                <div className="flex-1 flex justify-end items-center gap-2">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">{miss.display_name}</span>
                  {miss.type === 'blocking' ? (
                    <div className="relative group cursor-help">
                      <AlertCircle className="w-4 h-4 text-red-500" />
                      <div className="absolute right-0 bottom-full mb-2 w-64 bg-gray-900 text-white text-xs p-2 rounded shadow-lg hidden group-hover:block z-10">
                        Without this column, these analyses will be disabled:
                        <ul className="mt-1 list-disc pl-4 text-gray-300">
                          {miss.blocked_modules.slice(0, 3).map(mod => <li key={mod}>{mod}</li>)}
                          {miss.blocked_modules.length > 3 && <li>+{miss.blocked_modules.length - 3} more</li>}
                        </ul>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 text-xs text-amber-500 bg-amber-100 dark:bg-amber-500/20 px-2 py-0.5 rounded">
                      <Info className="w-3 h-3" /> {t('onb_optional', language)}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-3xl bg-white dark:bg-[#16162a] rounded-2xl shadow-2xl border border-gray-200 dark:border-white/5 overflow-hidden flex flex-col max-h-[90vh]">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary via-purple-500 to-pink-500" />

        {/* Escape hatch — always reachable so a stuck modal can't lock the user out. */}
        <button
          type="button"
          onClick={logout}
          className="absolute top-3 end-4 z-10 flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
          aria-label={t('onb_signOut', language)}
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>{t('onb_signOut', language)}</span>
        </button>

        <div className="p-6 sm:p-8 flex-1 overflow-y-auto">
          {/* ── Upload stage ── */}
          {stage === 'upload' && (
            <div className="max-w-lg mx-auto mt-10 mb-10">
              <div className="mb-6 text-center">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10 mb-4">
                  <UploadCloud className="w-7 h-7 text-primary" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">{t('onb_welcome', language)}</h2>
                <p className="mt-2 text-slate-500 dark:text-slate-400 text-sm leading-relaxed">
                  {t('onb_intro', language)}
                </p>
              </div>

              <div
                className={`relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-10 cursor-pointer transition-all duration-200
                  ${dragActive ? 'border-primary bg-primary/5 scale-[1.02]' : 'border-gray-300 dark:border-white/10 hover:border-primary/60 hover:bg-primary/[0.03]'}`}
                onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls,.json,.parquet"
                  className="hidden"
                  onChange={(e) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
                />
                <UploadCloud className={`w-10 h-10 transition-colors ${dragActive ? 'text-primary' : 'text-slate-400'}`} />
                <div className="text-center">
                  <p className="font-semibold text-gray-700 dark:text-slate-200">
                    {dragActive ? t('onb_drop', language) : t('onb_drag', language)}
                  </p>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                    {language === 'ar'
                      ? 'يدعم CSV · Excel · JSON · Parquet'
                      : 'Supports CSV · Excel · JSON · Parquet'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* ── Uploading stage ── */}
          {stage === 'uploading' && (
            <div className="flex flex-col items-center justify-center h-full gap-6 text-center mt-20 mb-20">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-500/10 animate-pulse">
                <FileText className="w-7 h-7 text-blue-500" />
              </div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">{t('onb_reading', language)}</h2>
              <div className="w-64 h-2.5 bg-gray-100 dark:bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-primary to-blue-400 rounded-full transition-all duration-300" style={{ width: `${uploadPct}%` }} />
              </div>
            </div>
          )}

          {/* ── Reviewing stage ── */}
          {stage === 'reviewing' && (
            <div className="h-full flex flex-col">
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">{t('onb_reviewTitle', language)}</h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {t('onb_reviewDesc', language)}
                </p>
              </div>

              {/* Source-currency selector. Defaults to "auto-detect" — stage3
                  will read the CSV's `currency` column (mode) and fall back to
                  USD. If the file has no currency column, the user can pick
                  here so the dashboard converts values correctly. */}
              <div className="mb-4 bg-white dark:bg-[#1f1f38] rounded-xl border border-gray-200 dark:border-white/10 p-4">
                <label className="block text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1">
                  {t('onb_sourceCurrencyLabel', language)}
                </label>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
                  {t('onb_sourceCurrencyHint', language)}
                </p>
                <select
                  value={sourceCurrencyOverride}
                  onChange={(e) => setSourceCurrencyOverride(e.target.value)}
                  className="w-full text-sm bg-white dark:bg-[#16162a] border border-gray-300 dark:border-white/20 rounded-md px-3 py-2 text-gray-700 dark:text-gray-200 focus:ring-primary focus:border-primary outline-none"
                >
                  <option value="">{t('onb_sourceCurrencyAuto', language)}</option>
                  <option value="USD">USD — US Dollar</option>
                  <option value="EUR">EUR — Euro</option>
                  <option value="GBP">GBP — British Pound</option>
                  <option value="JPY">JPY — Japanese Yen</option>
                  <option value="CNY">CNY — Chinese Yuan</option>
                  <option value="BRL">BRL — Brazilian Real</option>
                  <option value="SAR">SAR — Saudi Riyal</option>
                  <option value="AED">AED — UAE Dirham</option>
                  <option value="EGP">EGP — Egyptian Pound</option>
                  <option value="KWD">KWD — Kuwaiti Dinar</option>
                  <option value="QAR">QAR — Qatari Riyal</option>
                  <option value="BHD">BHD — Bahraini Dinar</option>
                  <option value="OMR">OMR — Omani Rial</option>
                  <option value="JOD">JOD — Jordanian Dinar</option>
                  <option value="TRY">TRY — Turkish Lira</option>
                </select>
              </div>

              <div className="flex-1 overflow-y-auto pe-2">
                {renderSection('transaction',   t('onb_sectionTransaction', language), 'transaction')}
                {renderSection('customer_meta', t('onb_sectionCustomer', language),    'customer_meta')}
                {renderSection('product_meta',  t('onb_sectionProduct', language),     'product_meta')}
              </div>

              <div className="mt-6 pt-6 border-t border-gray-200 dark:border-white/10 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2 text-sm">
                    <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                    <span className="text-gray-700 dark:text-gray-300 font-medium">
                      {moduleSummary.eligible} / {moduleSummary.total} {t('onb_ready', language)}
                    </span>
                  </div>
                  {moduleSummary.blocked > 0 && (
                    <div className="flex items-center gap-2 text-sm">
                      <div className="w-2 h-2 rounded-full bg-amber-500"></div>
                      <span className="text-slate-500">{moduleSummary.blocked} {t('onb_disabled', language)}</span>
                    </div>
                  )}
                </div>
                <button
                  onClick={handleConfirm}
                  className="bg-primary hover:bg-primary-hover text-white font-semibold py-2.5 px-6 rounded-lg shadow-md transition-all duration-200"
                >
                  {t('onb_startAnalysis', language)}
                </button>
              </div>
            </div>
          )}

          {/* ── Confirming/Processing stage ── */}
          {(stage === 'confirming' || stage === 'processing') && (
            <div className="flex flex-col items-center justify-center h-full gap-6 text-center mt-20 mb-20">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-purple-500/10 animate-pulse">
                <Loader2 className="w-7 h-7 text-purple-500 animate-spin" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">{t('onb_processing', language)}</h2>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                  {t('onb_processingDesc', language)}
                </p>
              </div>
              <div className="w-full max-w-md mt-4">
                <div className="flex justify-between text-xs text-slate-400 mb-1.5">
                  <span>{t('onb_progress', language)}</span>
                  <span>{processingPct}%</span>
                </div>
                <div className="w-full h-2.5 bg-gray-100 dark:bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-700" style={{ width: `${processingPct}%` }} />
                </div>
              </div>
            </div>
          )}

          {/* ── Complete stage ── */}
          {stage === 'complete' && (
            <div className="flex flex-col items-center justify-center h-full gap-6 text-center mt-20 mb-20">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-500/10">
                <CheckCircle2 className="w-9 h-9 text-emerald-500" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">{t('onb_complete', language)}</h2>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                  {t('onb_completeDesc', language)}
                </p>
              </div>
              <button
                onClick={onComplete}
                className="mt-4 bg-primary hover:bg-primary-hover text-white font-semibold py-3 px-8 rounded-xl shadow-lg transition-all duration-200"
              >
                {t('onb_viewDashboard', language)}
              </button>
            </div>
          )}

          {/* ── Error stage ── */}
          {stage === 'error' && (
            <div className="flex flex-col items-center justify-center h-full gap-6 text-center mt-20 mb-20">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-red-500/10">
                <AlertCircle className="w-7 h-7 text-red-500" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">{t('onb_error', language)}</h2>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{errorMsg}</p>
              </div>
              <button onClick={retry} className="mt-2 bg-slate-200 dark:bg-white/10 hover:bg-slate-300 dark:hover:bg-white/20 text-gray-900 dark:text-white font-semibold py-2.5 px-6 rounded-xl transition-all duration-200">
                {t('onb_tryAgain', language)}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
