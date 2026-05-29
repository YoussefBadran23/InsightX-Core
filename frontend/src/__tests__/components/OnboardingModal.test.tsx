import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { mockSniff, mockConfirm, mockGetSchema, mockGetStatus } = vi.hoisted(() => ({
  mockSniff: vi.fn(),
  mockConfirm: vi.fn(),
  mockGetSchema: vi.fn(),
  mockGetStatus: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  uploadApi: {
    sniffCsv: mockSniff,
    confirmMappings: mockConfirm,
    getSchemaColumns: mockGetSchema,
  },
  jobsApi: {
    getStatus: mockGetStatus,
  },
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (sel: (s: object) => unknown) =>
    sel({ logout: vi.fn(), user: null }),
}));

vi.mock('@/stores/uiStore', () => ({
  useUiStore: (sel: (s: object) => unknown) =>
    sel({ language: 'en' }),
}));

import { OnboardingModal } from '@/components/OnboardingModal';

const SNIFF_RESPONSE = {
  data: {
    sniff_id: 'sniff-1',
    mappings: [
      {
        csv_header: 'order_id',
        status: 'matched',
        internal_column: 'order_id',
        display_name: 'Order ID',
        group: 'transaction',
        confidence: 0.99,
        alternatives: [],
      },
    ],
    missing_columns: [],
    module_summary: { total: 39, eligible: 38, blocked: 1 },
  },
};

describe('OnboardingModal', () => {
  const onComplete = vi.fn();

  beforeEach(() => {
    onComplete.mockClear();
    mockSniff.mockReset();
    mockConfirm.mockReset();
    mockGetSchema.mockResolvedValue({ data: [] });
    mockGetStatus.mockResolvedValue({ data: { status: 'analyzing', progress: 50 } });
  });

  it('renders the welcome heading in upload stage', () => {
    render(<OnboardingModal onComplete={onComplete} />);
    expect(screen.getByText(/welcome to insightx/i)).toBeInTheDocument();
  });

  it('shows the drag & drop area', () => {
    render(<OnboardingModal onComplete={onComplete} />);
    expect(screen.getByText(/drag/i)).toBeInTheDocument();
  });

  it('shows Sign out escape hatch button', () => {
    render(<OnboardingModal onComplete={onComplete} />);
    expect(screen.getByLabelText(/sign out/i)).toBeInTheDocument();
  });

  it('transitions to reviewing stage after successful sniff', async () => {
    mockSniff.mockResolvedValueOnce(SNIFF_RESPONSE);
    render(<OnboardingModal onComplete={onComplete} />);

    const file = new File(['a,b\n1,2'], 'data.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/review data mappings/i)).toBeInTheDocument();
    });
  });

  it('shows error stage when sniff fails', async () => {
    mockSniff.mockRejectedValue(new Error('network error'));
    render(<OnboardingModal onComplete={onComplete} />);

    const file = new File(['a,b\n1,2'], 'data.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });
  });

  it('retry button resets back to upload stage', async () => {
    mockSniff.mockRejectedValue(new Error('fail'));
    render(<OnboardingModal onComplete={onComplete} />);

    const file = new File(['a,b\n1,2'], 'data.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => screen.getByText(/something went wrong/i));
    fireEvent.click(screen.getByText(/try again/i));
    expect(screen.getByText(/welcome to insightx/i)).toBeInTheDocument();
  });

  it('rejects non-CSV file types', async () => {
    render(<OnboardingModal onComplete={onComplete} />);
    const file = new File(['garbage'], 'data.exe', { type: 'application/octet-stream' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });
    expect(mockSniff).not.toHaveBeenCalled();
  });

  it('calls onComplete when analysis finishes', async () => {
    mockSniff.mockResolvedValueOnce(SNIFF_RESPONSE);
    mockConfirm.mockResolvedValueOnce({ data: { job_id: 'job-1' } });
    mockGetStatus
      .mockResolvedValueOnce({ data: { status: 'analyzing', progress: 50 } })
      .mockResolvedValueOnce({ data: { status: 'completed', progress: 100 } });

    render(<OnboardingModal onComplete={onComplete} />);

    const file = new File(['a,b\n1,2'], 'data.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => screen.getByText(/review data mappings/i));

    fireEvent.click(screen.getByText(/start analysis/i));
    await waitFor(() => screen.getByText(/analysis complete/i), { timeout: 5000 });

    fireEvent.click(screen.getByText(/view dashboard/i));
    expect(onComplete).toHaveBeenCalledOnce();
  });
});
