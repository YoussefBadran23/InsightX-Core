import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

const {
  mockKpiSummary, mockKpiHistory, mockJobsList, mockAnalyticsGet, mockRouterPush,
} = vi.hoisted(() => ({
  mockKpiSummary: vi.fn(),
  mockKpiHistory: vi.fn(),
  mockJobsList: vi.fn(),
  mockAnalyticsGet: vi.fn(),
  mockRouterPush: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  kpiApi: { summary: mockKpiSummary, history: mockKpiHistory },
  analyticsApi: { get: mockAnalyticsGet },
  jobsApi: { list: mockJobsList },
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (sel: (s: object) => unknown) =>
    sel({ user: { preferred_currency: 'USD' }, token: 'tok', isAuthenticated: true }),
}));

vi.mock('@/stores/uiStore', () => ({
  useUiStore: (sel?: (s: object) => unknown) => {
    const state = { language: 'en' };
    return sel ? sel(state) : state;
  },
}));

vi.mock('@/stores/jobStore', () => ({
  useJobStore: (sel: (s: object) => unknown) =>
    sel({ sourceCurrency: 'USD', setSourceCurrency: vi.fn() }),
}));

vi.mock('@/stores/dashboardStore', () => ({
  useDashboardStore: (sel: (s: object) => unknown) =>
    sel({ savedWidgets: [], widgets: [] }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockRouterPush, replace: vi.fn() }),
  usePathname: () => '/dashboard',
}));

vi.mock('recharts', () => ({
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
}));

vi.mock('@/components/charts/ChartCard', () => ({ ChartCard: () => null }));
vi.mock('@/components/charts/foundation/InsightCard', () => ({
  InsightCard: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div><h3>{title}</h3>{children}</div>
  ),
}));
vi.mock('@/components/charts/foundation/InsightTooltip', () => ({ InsightTooltip: () => null }));
vi.mock('@/components/charts/chartHelpers', () => ({
  useChartTheme: () => ({
    isDark: false,
    semantic: { brand: '#6366f1' },
    semanticSoft: { brand: '#e0e7ff' },
    text: { muted: '#94a3b8', body: '#1e293b' },
    gridStroke: '#e2e8f0',
    surface: '#ffffff',
    surfaceMuted: '#f8fafc',
  }),
}));
vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

const KPI_RESPONSE = {
  data: {
    total_revenue: 150000,
    active_customers: 320,
    churn_rate: 2.5,
    source_currency: 'USD',
    revenue_delta: { change_pct: 12, direction: 'up', current: 150000, previous: 133929 },
    customers_delta: null,
    orders_delta: null,
    aov_delta: null,
    snapshot_date: '2026-05-27',
    new_customers: 50,
    total_orders: 890,
    avg_order_value: 168.5,
    revenue_na: 100000,
    revenue_eu: 30000,
    revenue_apac: 20000,
    revenue_latam: 0,
  },
};

describe('DashboardHome page', () => {
  beforeEach(() => {
    mockKpiSummary.mockReset();
    mockKpiHistory.mockReset();
    mockJobsList.mockReset();
    mockAnalyticsGet.mockReset();
    mockRouterPush.mockReset();

    mockKpiSummary.mockResolvedValue(KPI_RESPONSE);
    mockKpiHistory.mockResolvedValue({ data: { days: 30, items: [] } });
    mockJobsList.mockResolvedValue({ data: { items: [] } });
    mockAnalyticsGet.mockRejectedValue(new Error('no data'));
  });

  it('shows a spinner while loading', async () => {
    mockKpiSummary.mockReturnValue(new Promise(() => {}));
    const { default: DashboardHome } = await import('@/app/dashboard/page');
    render(<DashboardHome />);
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('renders KPI cards after data loads', async () => {
    const { default: DashboardHome } = await import('@/app/dashboard/page');
    render(<DashboardHome />);
    await waitFor(() => {
      expect(screen.getByText(/total revenue/i)).toBeInTheDocument();
      expect(screen.getByText(/active customers/i)).toBeInTheDocument();
      expect(screen.getByText(/churn rate/i)).toBeInTheDocument();
    });
  });

  it('shows customer count formatted', async () => {
    const { default: DashboardHome } = await import('@/app/dashboard/page');
    render(<DashboardHome />);
    await waitFor(() => {
      expect(screen.getByText('320')).toBeInTheDocument();
    });
  });

  it('redirects to upload when KPI returns all zeros', async () => {
    mockKpiSummary.mockResolvedValue({
      data: { ...KPI_RESPONSE.data, total_revenue: 0, active_customers: 0 },
    });
    const { default: DashboardHome } = await import('@/app/dashboard/page');
    render(<DashboardHome />);
    await waitFor(() => {
      expect(mockRouterPush).toHaveBeenCalledWith('/dashboard/upload');
    });
  });
});
