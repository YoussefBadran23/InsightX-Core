import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('@/lib/api', () => ({
  jobsApi: {
    getStatus: vi.fn(),
  },
}));

describe('jobStore', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('has correct initial state', async () => {
    const { useJobStore } = await import('@/stores/jobStore');
    const state = useJobStore.getState();
    expect(state.currentJob).toBeNull();
    expect(state.uploadProgress).toBe(0);
    expect(state.isPolling).toBe(false);
    expect(state.sourceCurrency).toBe('USD');
  });

  it('setCurrentJob updates currentJob', async () => {
    const { useJobStore } = await import('@/stores/jobStore');
    const fakeJob = { id: 'job-1', status: 'completed' } as never;
    useJobStore.getState().setCurrentJob(fakeJob);
    expect(useJobStore.getState().currentJob).toEqual(fakeJob);
  });

  it('setUploadProgress clamps to provided value', async () => {
    const { useJobStore } = await import('@/stores/jobStore');
    useJobStore.getState().setUploadProgress(55);
    expect(useJobStore.getState().uploadProgress).toBe(55);
  });

  it('setSourceCurrency uppercases and stores the value', async () => {
    const { useJobStore } = await import('@/stores/jobStore');
    useJobStore.getState().setSourceCurrency('eur');
    expect(useJobStore.getState().sourceCurrency).toBe('EUR');
  });

  it('setSourceCurrency defaults to USD on empty string', async () => {
    const { useJobStore } = await import('@/stores/jobStore');
    useJobStore.getState().setSourceCurrency('');
    expect(useJobStore.getState().sourceCurrency).toBe('USD');
  });

  it('reset clears job and progress', async () => {
    const { useJobStore } = await import('@/stores/jobStore');
    const fakeJob = { id: 'j1' } as never;
    useJobStore.getState().setCurrentJob(fakeJob);
    useJobStore.getState().setUploadProgress(80);
    useJobStore.getState().reset();
    expect(useJobStore.getState().currentJob).toBeNull();
    expect(useJobStore.getState().uploadProgress).toBe(0);
    expect(useJobStore.getState().isPolling).toBe(false);
  });

  it('startPolling sets isPolling to true', async () => {
    const { jobsApi } = await import('@/lib/api');
    (jobsApi.getStatus as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { status: 'analyzing', progress: 30 },
    });
    const { useJobStore } = await import('@/stores/jobStore');
    useJobStore.getState().startPolling('job-123');
    expect(useJobStore.getState().isPolling).toBe(true);
    useJobStore.getState().stopPolling();
  });

  it('stopPolling sets isPolling to false', async () => {
    const { useJobStore } = await import('@/stores/jobStore');
    useJobStore.getState().stopPolling();
    expect(useJobStore.getState().isPolling).toBe(false);
  });

  it('calls onComplete when job reaches terminal status', async () => {
    const { jobsApi } = await import('@/lib/api');
    (jobsApi.getStatus as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { id: 'job-x', status: 'completed', source_currency: 'BRL' },
    });
    const { useJobStore } = await import('@/stores/jobStore');
    const onComplete = vi.fn();
    useJobStore.getState().startPolling('job-x', onComplete);
    await vi.runAllTimersAsync();
    expect(onComplete).toHaveBeenCalled();
    expect(useJobStore.getState().sourceCurrency).toBe('BRL');
  });
});
