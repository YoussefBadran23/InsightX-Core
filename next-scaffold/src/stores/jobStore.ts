// Zustand job store for upload flow polling
import { create } from 'zustand';
import type { UploadJob } from '@/types';
import { jobsApi } from '@/lib/api';

interface JobState {
  currentJob: UploadJob | null;
  uploadProgress: number; // 0–100 (file upload progress)
  isPolling: boolean;
  pollingInterval: ReturnType<typeof setInterval> | null;

  setCurrentJob: (job: UploadJob | null) => void;
  setUploadProgress: (pct: number) => void;
  startPolling: (jobId: string, onComplete?: (job: UploadJob) => void) => void;
  stopPolling: () => void;
  reset: () => void;
}

const TERMINAL_STATUSES = new Set(['completed', 'failed']);

export const useJobStore = create<JobState>((set, get) => ({
  currentJob: null,
  uploadProgress: 0,
  isPolling: false,
  pollingInterval: null,

  setCurrentJob: (job) => set({ currentJob: job }),
  setUploadProgress: (pct) => set({ uploadProgress: pct }),

  startPolling: (jobId, onComplete) => {
    const { pollingInterval } = get();
    if (pollingInterval) clearInterval(pollingInterval);

    set({ isPolling: true });

    const interval = setInterval(async () => {
      try {
        const resp = await jobsApi.getStatus(jobId);
        const job: UploadJob = resp.data;
        set({ currentJob: job });

        if (TERMINAL_STATUSES.has(job.status)) {
          get().stopPolling();
          onComplete?.(job);
        }
      } catch {
        // silently ignore poll errors — network blip
      }
    }, 2000);

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
