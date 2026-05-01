'use client';

/**
 * Providers — client-side initialization layer.
 *
 * Responsibilities:
 *  1. Apply theme class & language dir on mount (prevents FOUC for dynamic changes)
 *  2. Validate the persisted JWT session on first load (fetchMe)
 *  3. Auto-redirect authenticated users from '/' to '/dashboard'
 */

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore, applyTheme, applyLanguage } from '@/stores/uiStore';

export function Providers({ children }: { children: React.ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname();

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

  // ── 3. Auto-redirect: if authenticated user lands on '/' send to dashboard ─
  useEffect(() => {
    if (isAuthenticated && pathname === '/') {
      router.replace('/dashboard');
    }
  }, [isAuthenticated, pathname, router]);

  return <>{children}</>;
}
