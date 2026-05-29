// Zustand job store for upload flow polling
import { create } from 'zustand';
import type { UploadJob } from '@/types';
import { jobsApi } from '@/lib/api';

interface JobState {
  currentJob: UploadJob | null;
  uploadProgress: number; // 0–100 (file upload progress)
  isPolling: boolean;
  pollingInterval: ReturnType<typeof setInterval> | null;

  /**
   * Native currency of the most recently completed upload (ISO 4217).
   * Hydrated by DashboardLayout on mount via `/kpi/summary` and used as the
   * `from` argument to `formatMoney` across every dashboard page — that's how
   * Olist (BRL) data viewed by an EGP user gets converted end-to-end instead
   * of just having the symbol swapped.
   */
  sourceCurrency: string;

  setCurrentJob: (job: UploadJob | null) => void;
  setUploadProgress: (pct: number) => void;
  setSourceCurrency: (currency: string) => void;
  startPolling: (jobId: string, onComplete?: (job: UploadJob) => void) => void;
  stopPolling: () => void;
  reset: () => void;
}

const TERMINAL_STATUSES = new Set(['completed', 'completed_with_errors', 'failed']);

export const useJobStore = create<JobState>((set, get) => ({
  currentJob: null,
  uploadProgress: 0,
  isPolling: false,
  pollingInterval: null,
  sourceCurrency: 'USD',

  setCurrentJob: (job) => set({ currentJob: job }),
  setUploadProgress: (pct) => set({ uploadProgress: pct }),
  setSourceCurrency: (currency) => {
    const next = (currency || 'USD').toUpperCase();
    set({ sourceCurrency: next });
  },

  startPolling: (jobId, onComplete) => {
    const { pollingInterval } = get();
    if (pollingInterval) clearInterval(pollingInterval);

    set({ isPolling: true });

    const interval = setInterval(async () => {
      try {
        const resp = await jobsApi.getStatus(jobId);
        const job: UploadJob = resp.data;
        set({ currentJob: job });
        // Keep the source currency fresh: if the polling response carries a
        // source_currency (stage3 has populated it), reflect it immediately
        // so pages already mounted pick up the conversion on the next render.
        if (job?.source_currency) {
          set({ sourceCurrency: job.source_currency.toUpperCase() });
        }

        if (TERMINAL_STATUSES.has(job.status)) {
          get().stopPolling();
          onComplete?.(job);
        }
      } catch {
        // silently ignore poll errors — network blip
      }
    }, 1000);

    set({ pollingInterval: interval });
  },

  stopPolling: () => {
    const { pollingInterval } = get();
    if (pollingInterval) clearInterval(pollingInterval);
    set({ isPolling: false, pollingInterval: null });
  },

  reset: () => {
    get().stopPolling();
    set({ currentJob: null, uploadProgress: 0, isPolling: false });
  },
}));
