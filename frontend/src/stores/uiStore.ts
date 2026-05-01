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

// Apply language/direction to <html> element
export function applyLanguage(lang: Language) {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
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
        // Sync to backend only if authenticated
        const { isAuthenticated } = useAuthStore.getState();
        if (isAuthenticated) {
          try {
            authApi.updateMe({ preferred_theme: theme });
          } catch { /* ignore */ }
        }
      },

      toggleTheme: () => {
        const next = get().theme === 'light' ? 'dark' : 'light';
        set({ theme: next });
        applyTheme(next);
        const { isAuthenticated } = useAuthStore.getState();
        if (isAuthenticated) {
          try {
            authApi.updateMe({ preferred_theme: next });
          } catch { /* ignore */ }
        }
      },

      setLanguage: (language) => {
        set({ language });
        applyLanguage(language);
        setLangCookie(language);
        const { isAuthenticated } = useAuthStore.getState();
        if (isAuthenticated) {
          try {
            authApi.updateMe({ preferred_language: language });
          } catch { /* ignore */ }
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
