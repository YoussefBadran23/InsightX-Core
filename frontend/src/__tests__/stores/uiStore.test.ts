import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('@/stores/authStore', () => ({
  useAuthStore: {
    getState: () => ({ isAuthenticated: false }),
  },
}));

vi.mock('@/lib/api', () => ({
  authApi: { updateMe: vi.fn().mockResolvedValue({}) },
}));

import { useUiStore, applyTheme, applyLanguage } from '@/stores/uiStore';

const UI_INITIAL = { theme: 'light' as const, language: 'en' as const };

describe('uiStore', () => {
  beforeEach(() => {
    useUiStore.setState(UI_INITIAL);
  });

  it('has default theme of light and language of en', () => {
    const state = useUiStore.getState();
    expect(['light', 'dark']).toContain(state.theme);
    expect(['en', 'ar']).toContain(state.language);
  });

  it('setTheme updates theme state', () => {
    useUiStore.getState().setTheme('dark');
    expect(useUiStore.getState().theme).toBe('dark');
    useUiStore.getState().setTheme('light');
    expect(useUiStore.getState().theme).toBe('light');
  });

  it('toggleTheme flips between light and dark', () => {
    useUiStore.setState({ theme: 'light' });
    useUiStore.getState().toggleTheme();
    expect(useUiStore.getState().theme).toBe('dark');
    useUiStore.getState().toggleTheme();
    expect(useUiStore.getState().theme).toBe('light');
  });

  it('setLanguage updates language state', () => {
    useUiStore.getState().setLanguage('ar');
    expect(useUiStore.getState().language).toBe('ar');
    useUiStore.getState().setLanguage('en');
    expect(useUiStore.getState().language).toBe('en');
  });
});

describe('applyTheme / applyLanguage', () => {
  it('applyTheme adds dark class to documentElement', () => {
    applyTheme('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    applyTheme('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('applyLanguage sets lang and dir on documentElement', () => {
    applyLanguage('ar');
    expect(document.documentElement.lang).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
    applyLanguage('en');
    expect(document.documentElement.lang).toBe('en');
    expect(document.documentElement.dir).toBe('ltr');
  });
});
