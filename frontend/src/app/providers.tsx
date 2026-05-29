'use client';

/**
 * Providers — client-side initialization layer.
 *
 * Responsibilities:
 *  1. Apply theme class & language dir on mount (prevents FOUC for dynamic changes)
 *  2. Validate the persisted JWT session on first load (fetchMe)
 *
 * NOTE: We intentionally do NOT auto-redirect authenticated users away from
 * `/`. The landing page should always be reachable; the PublicHeader on `/`
 * shows a "View Dashboard" CTA when the user is logged in, which is the
 * explicit, non-surprising way to enter the app.
 */

import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore, applyTheme, applyLanguage } from '@/stores/uiStore';

export function Providers({ children }: { children: React.ReactNode }) {
  const { theme, language } = useUiStore();
  const { token, isAuthenticated, fetchMe } = useAuthStore();

  // ── 1. Sync theme & language to DOM on mount and when they change ──────────
  useEffect(() => {
    applyTheme(theme);
    applyLanguage(language);
  }, [theme, language]);

  // ── 2. Validate persisted token on mount ──────────────────────────────────
  useEffect(() => {
    if (token && !isAuthenticated) {
      // Token exists in localStorage but Zustand state was reset → re-validate
      fetchMe().catch(() => {
        // fetchMe already clears state on 401, nothing to do here
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <>{children}</>;
}
