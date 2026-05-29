import { describe, it, expect, beforeEach, vi } from 'vitest';

const { mockLogin, mockMe } = vi.hoisted(() => ({
  mockLogin: vi.fn(),
  mockMe: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  authApi: {
    login: mockLogin,
    register: vi.fn(),
    me: mockMe,
    updateMe: vi.fn().mockResolvedValue({}),
  },
}));

import { useAuthStore } from '@/stores/authStore';

const INITIAL = { token: null, user: null, isAuthenticated: false, isLoading: false };

describe('authStore', () => {
  beforeEach(() => {
    useAuthStore.setState(INITIAL);
    mockLogin.mockReset();
    mockMe.mockReset();
  });

  it('starts with null token and not authenticated', () => {
    const s = useAuthStore.getState();
    expect(s.token).toBeNull();
    expect(s.isAuthenticated).toBe(false);
    expect(s.user).toBeNull();
  });

  it('setToken stores the token and marks isAuthenticated', () => {
    useAuthStore.getState().setToken('tok-abc');
    expect(useAuthStore.getState().token).toBe('tok-abc');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('login calls authApi.login and fetchMe on success', async () => {
    mockLogin.mockResolvedValueOnce({ data: { access_token: 'jwt-xyz' } });
    mockMe.mockResolvedValueOnce({ data: { id: 'u1', email: 'a@b.com', full_name: 'Alice' } });
    await useAuthStore.getState().login('a@b.com', 'pass');
    expect(mockLogin).toHaveBeenCalledWith('a@b.com', 'pass');
    expect(useAuthStore.getState().token).toBe('jwt-xyz');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().user?.email).toBe('a@b.com');
  });

  it('login resets isLoading to false on error', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Network error'));
    await expect(useAuthStore.getState().login('a@b.com', 'bad')).rejects.toThrow();
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it('fetchMe clears state on error', async () => {
    mockMe.mockRejectedValueOnce(new Error('unauthorized'));
    useAuthStore.setState({ token: 'old', isAuthenticated: true });
    await useAuthStore.getState().fetchMe();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('logout clears token, user, and isAuthenticated', () => {
    useAuthStore.setState({ token: 'tok', user: { id: 'u1' } as never, isAuthenticated: true });
    // Suppress window.location redirect
    const origLocation = window.location;
    Object.defineProperty(window, 'location', { writable: true, value: { href: '' } });
    useAuthStore.getState().logout();
    Object.defineProperty(window, 'location', { writable: true, value: origLocation });
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
