// Axios API client with JWT interceptor and error handling
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import * as Sentry from "@sentry/nextjs";

let baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
if (!baseUrl || baseUrl.trim() === '') baseUrl = 'http://localhost:8000';
if (baseUrl.endsWith('/')) baseUrl = baseUrl.slice(0, -1);
if (!baseUrl.endsWith('/api/v1')) baseUrl += '/api/v1';
const BASE_URL = baseUrl;

export const api = axios.create({
  baseURL: BASE_URL,
  // 30s was tripping cold-start sentence-transformers loads on /upload/sniff
  // and large CSV ingestion on /upload/confirm. 90s is generous enough for a
  // 100MB CSV on a slow Docker Desktop machine but still fails fast for real
  // dead-backend situations.
  timeout: 90000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Request interceptor: attach JWT ────────────────────────────────────────
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('insightx_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor: handle 401 → redirect to login ──────────────────
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Log error to Sentry
    Sentry.captureException(error);

    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('insightx_token');
      localStorage.removeItem('insightx_user');
      // Clear the auth cookie too — middleware reads from the cookie. If we
      // only clear localStorage, the user gets bounced back to /dashboard
      // by the middleware and ends up stuck on the OnboardingModal.
      document.cookie = 'insightx_token=; path=/; max-age=0; SameSite=Lax';
      // Don't trigger redirect loops on auth pages or the landing page.
      const safePaths = ['/login', '/signup', '/forgot-password', '/reset-password', '/'];
      const isSafe = safePaths.some((p) => window.location.pathname === p || window.location.pathname.startsWith(p + '/'));
      if (!isSafe) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// ── Typed API helpers ──────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string; expires_in: number }>('/auth/login', { email, password }),

  register: (email: string, password: string, full_name: string) =>
    api.post('/auth/register', { email, password, full_name }),

  me: () => api.get('/auth/me'),

  updateMe: (data: {
    full_name?: string;
    avatar_url?: string;
    company_name?: string;
    company_logo_url?: string | null;
    preferred_theme?: string;
    preferred_language?: string;
    preferred_currency?: string;
  }) => api.patch('/auth/me', data),

  changePassword: (current_password: string, new_password: string) =>
    api.post('/auth/change-password', { current_password, new_password }),

  forgotPassword: (email: string) =>
    api.post('/auth/forgot-password', { email }),

  resetPassword: (token: string, new_password: string) =>
    api.post('/auth/reset-password', { token, new_password }),
};

export const jobsApi = {
  list: (page = 1, pageSize = 20) =>
    api.get('/jobs', { params: { page, page_size: pageSize } }),

  get: (jobId: string) =>
    api.get(`/jobs/${jobId}`),

  getStatus: (jobId: string) =>
    api.get(`/jobs/${jobId}/status`),

  getModules: (jobId: string) =>
    api.get(`/jobs/${jobId}/modules`),

  delete: (jobId: string) =>
    api.delete(`/jobs/${jobId}`),
};

export const uploadApi = {
  sniffCsv: (file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData();
    form.append('file', file);
    return api.post('/upload/sniff', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      },
    });
  },

  confirmMappings: (data: {
    sniff_id: string;
    confirmed_mappings: { csv_header: string; internal_column: string | null }[];
    /** Optional ISO 4217 user override; omit to let stage3 detect from the CSV. */
    source_currency?: string;
  }) => api.post('/upload/confirm', data),

  getSchemaColumns: () => api.get('/upload/schema/columns'),
};

export const analyticsApi = {
  get: (type: string, jobId?: string) =>
    api.get(`/analytics/${type}`, { params: jobId ? { job_id: jobId } : {} }),

  summary: (jobId?: string) =>
    api.get('/analytics/summary', { params: jobId ? { job_id: jobId } : {} }),
};

export const kpiApi = {
  summary: () => api.get('/kpi/summary'),
  history: (days = 30) => api.get('/kpi/history', { params: { days } }),
};

export const customersApi = {
  list: (params: {
    page?: number;
    page_size?: number;
    search?: string;
    segment?: string;
    region?: string;
    sort_by?: string;
    sort_dir?: string;
  }) => api.get('/customers', { params }),

  get: (customerId: string) => api.get(`/customers/${customerId}`),
};

export const productsApi = {
  list: (params: {
    page?: number;
    page_size?: number;
    search?: string;
    category?: string;
    abc_tier?: string;
    low_stock_only?: boolean;
    sort_by?: string;
    sort_dir?: string;
  }) => api.get('/products', { params }),

  get: (productId: string) => api.get(`/products/${productId}`),
};

export const forecastsApi = {
  latest: () => api.get('/forecasts/latest'),
  getByJob: (jobId: string) => api.get(`/forecasts/${jobId}`),
  scenario: (params: {
    marketing_spend_pct: number;
    price_shift_pct: number;
    seasonal_adjustment: string;
    job_id?: string;
  }) => api.post('/forecasts/scenario', params),
};

export const insightsApi = {
  latest: () => api.get('/insights/latest'),
  getByJob: (jobId: string) => api.get(`/insights/${jobId}`),
};
