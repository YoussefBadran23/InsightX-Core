// Zustand store for global UI state: theme + language
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';

export type Theme = 'light' | 'dark';
export type Language = 'en' | 'ar';

interface UiState {
  theme: Theme;
  language: Language;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setLanguage: (lang: Language) => void;
}

// Apply theme class to <html> element
export function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return;
  const html = document.documentElement;
  if (theme === 'dark') {
    html.classList.add('dark');
    html.classList.remove('light');
  } else {
    html.classList.remove('dark');
    html.classList.add('light');
  }
}

// Apply language to <html> element.
// dir is intentionally always "ltr" — layout never mirrors for Arabic.
export function applyLanguage(lang: Language) {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = lang;
}

// Helper to write/clear language cookie
const setLangCookie = (lang: string) => {
  if (typeof document === 'undefined') return;
  document.cookie = `insightx_lang=${lang}; path=/; max-age=31536000; SameSite=Lax`;
};

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      theme: 'light',
      language: 'en',

      setTheme: (theme) => {
        set({ theme });
        applyTheme(theme);
        // Sync to backend only if authenticated. Note: `isAuthenticated` can
        // be stale (e.g. token expired but store not yet flushed) — we use
        // `.catch()` to swallow the resulting 401/403 silently so the
        // preference change still feels instant in the UI.
        const { isAuthenticated } = useAuthStore.getState();
        if (isAuthenticated) {
          authApi.updateMe({ preferred_theme: theme }).catch(() => {});
        }
      },

      toggleTheme: () => {
        const next = get().theme === 'light' ? 'dark' : 'light';
        set({ theme: next });
        applyTheme(next);
        const { isAuthenticated } = useAuthStore.getState();
        if (isAuthenticated) {
          authApi.updateMe({ preferred_theme: next }).catch(() => {});
        }
      },

      setLanguage: (language) => {
        set({ language });
        applyLanguage(language);
        setLangCookie(language);
        const { isAuthenticated } = useAuthStore.getState();
        if (isAuthenticated) {
          authApi.updateMe({ preferred_language: language }).catch(() => {});
        }
      },
    }),
    {
      name: 'insightx-ui',
      // Only persist these fields to localStorage
      partialize: (state) => ({ theme: state.theme, language: state.language }),
    }
  )
);
