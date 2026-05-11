// Zustand auth store with localStorage persistence
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types';
import { authApi } from '@/lib/api';

interface AuthState {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  setToken: (token: string) => void;
}

// Helper to write/clear the auth cookie so Next.js middleware can read it
const setAuthCookie = (token: string | null) => {
  if (typeof document === 'undefined') return;
  if (token) {
    document.cookie = `insightx_token=${token}; path=/; max-age=604800; SameSite=Lax`;
  } else {
    document.cookie = 'insightx_token=; path=/; max-age=0';
  }
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoading: false,
      isAuthenticated: false,

      setToken: (token: string) => {
        set({ token, isAuthenticated: true });
        if (typeof window !== 'undefined') {
          localStorage.setItem('insightx_token', token);
          setAuthCookie(token);
        }
      },

      login: async (email, password) => {
        set({ isLoading: true });
        try {
          const response = await authApi.login(email, password);
          const { access_token } = response.data;
          if (typeof window !== 'undefined') {
            localStorage.setItem('insightx_token', access_token);
            setAuthCookie(access_token);
          }
          set({ token: access_token, isAuthenticated: true });
          await get().fetchMe();
        } finally {
          set({ isLoading: false });
        }
      },

      register: async (email, password, fullName) => {
        set({ isLoading: true });
        try {
          const response = await authApi.register(email, password, fullName);
          // Backend returns RegisterResponse: { user, access_token, expires_in }
          const { access_token, user } = response.data as { access_token: string; user: User; expires_in: number };
          if (typeof window !== 'undefined') {
            localStorage.setItem('insightx_token', access_token);
            setAuthCookie(access_token);
          }
          set({ token: access_token, user, isAuthenticated: true });
          // Fetch full user profile to ensure all fields are populated
          await get().fetchMe();
        } finally {
          set({ isLoading: false });
        }
      },

      logout: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('insightx_token');
          localStorage.removeItem('insightx_user');
          setAuthCookie(null);
        }
        set({ token: null, user: null, isAuthenticated: false });
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
      },

      fetchMe: async () => {
        try {
          const response = await authApi.me();
          set({ user: response.data, isAuthenticated: true });
        } catch {
          // Token is invalid/expired — fully tear down auth state so the
          // user can re-authenticate. Without clearing the cookie here,
          // the middleware still considers them "logged in" and keeps
          // them on /dashboard with a stuck OnboardingModal.
          if (typeof window !== 'undefined') {
            localStorage.removeItem('insightx_token');
            localStorage.removeItem('insightx_user');
            setAuthCookie(null);
          }
          set({ token: null, user: null, isAuthenticated: false });
        }
      },
    }),
    {
      name: 'insightx-auth',
      partialize: (state) => ({ token: state.token, user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);
