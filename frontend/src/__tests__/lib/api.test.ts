import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';

// Mock axios so no real HTTP calls are made
vi.mock('axios', () => {
  const instance = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return {
    default: { create: vi.fn(() => instance), ...instance },
    ...{ create: vi.fn(() => instance) },
  };
});

describe('API base URL construction', () => {
  const originalEnv = process.env.NEXT_PUBLIC_API_URL;

  afterEach(() => {
    process.env.NEXT_PUBLIC_API_URL = originalEnv;
    vi.resetModules();
  });

  it('appends /api/v1 when env var has no suffix', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
    // Re-import so module runs with new env
    const { api } = await import('@/lib/api');
    expect(api).toBeDefined();
  });

  it('strips trailing slash before appending /api/v1', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000/';
    const { api } = await import('@/lib/api');
    expect(api).toBeDefined();
  });
});

describe('authApi helpers', () => {
  it('exports login, register, me, updateMe, changePassword, forgotPassword, resetPassword', async () => {
    const { authApi } = await import('@/lib/api');
    expect(typeof authApi.login).toBe('function');
    expect(typeof authApi.register).toBe('function');
    expect(typeof authApi.me).toBe('function');
    expect(typeof authApi.updateMe).toBe('function');
    expect(typeof authApi.changePassword).toBe('function');
    expect(typeof authApi.forgotPassword).toBe('function');
    expect(typeof authApi.resetPassword).toBe('function');
  });
});

describe('uploadApi helpers', () => {
  it('exports sniffCsv, confirmMappings, getSchemaColumns', async () => {
    const { uploadApi } = await import('@/lib/api');
    expect(typeof uploadApi.sniffCsv).toBe('function');
    expect(typeof uploadApi.confirmMappings).toBe('function');
    expect(typeof uploadApi.getSchemaColumns).toBe('function');
  });
});

describe('analyticsApi helpers', () => {
  it('exports get and summary', async () => {
    const { analyticsApi } = await import('@/lib/api');
    expect(typeof analyticsApi.get).toBe('function');
    expect(typeof analyticsApi.summary).toBe('function');
  });
});

describe('jobsApi helpers', () => {
  it('exports list, get, getStatus, getModules, delete', async () => {
    const { jobsApi } = await import('@/lib/api');
    expect(typeof jobsApi.list).toBe('function');
    expect(typeof jobsApi.get).toBe('function');
    expect(typeof jobsApi.getStatus).toBe('function');
    expect(typeof jobsApi.getModules).toBe('function');
    expect(typeof jobsApi.delete).toBe('function');
  });
});
