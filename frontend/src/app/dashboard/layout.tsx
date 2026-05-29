'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Home, Package, Users, BarChart3, TrendingUp, PieChart, Settings,
  Bell, LogOut, User, Sun, Moon, Globe, ChevronDown, Check, Menu, X as XIcon,
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { useJobStore } from '@/stores/jobStore';
import { t, type Locale } from '@/lib/i18n';
import { useState, useRef, useEffect } from 'react';
import { jobsApi, kpiApi } from '@/lib/api';
import { OnboardingModal } from '@/components/OnboardingModal';

const LANGUAGES: { code: Locale; label: string; flag: string }[] = [
  { code: 'en', label: 'English', flag: '🇬🇧' },
  { code: 'ar', label: 'العربية',  flag: '🇸🇦' },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, token, logout } = useAuthStore();
  const { theme, language, toggleTheme, setLanguage } = useUiStore();

  const setSourceCurrency = useJobStore((s) => s.setSourceCurrency);

  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isLangOpen, setIsLangOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const profileRef       = useRef<HTMLDivElement>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);
  const langRef          = useRef<HTMLDivElement>(null);

  const isDark = theme === 'dark';

  // Nav links — labels resolved against current language.
  const navLinks = [
    { name: t('nav_home', language),         href: '/dashboard',              icon: Home },
    { name: t('nav_products', language),     href: '/dashboard/products',     icon: Package },
    { name: t('nav_customers', language),    href: '/dashboard/customers',    icon: Users },
    { name: t('nav_analytics', language),    href: '/dashboard/analytics',    icon: BarChart3 },
    { name: t('nav_forecasting', language),  href: '/dashboard/forecasting',  icon: TrendingUp },
    { name: t('nav_segmentation', language), href: '/dashboard/segmentation', icon: PieChart },
  ];

  // ── Guard: bounce to /login if auth state is torn down (handles in-place 401) ──
  useEffect(() => {
    if (!token && !isAuthenticated) {
      setShowOnboarding(false);
      router.replace('/login');
    }
  }, [token, isAuthenticated, router]);

  // ── Show onboarding only if user is loaded AND has no completed jobs ──
  useEffect(() => {
    if (!user?.id || !isAuthenticated) {
      setShowOnboarding(false);
      return;
    }
    const key = `insightx_onboarded_${user.id}`;
    if (typeof window !== 'undefined' && localStorage.getItem(key)) return;
    jobsApi.list(1, 1)
      .then((res) => {
        const jobs = (res.data as any)?.jobs ?? res.data ?? [];
        const hasCompleted = Array.isArray(jobs) && jobs.some((j: any) => j.status === 'completed');
        if (!hasCompleted) setShowOnboarding(true);
      })
      .catch((err) => {
        if (err?.response?.status === 401) return;
        setShowOnboarding(true);
      });
  }, [user?.id, isAuthenticated]);

  // ── Hydrate the source currency once per session ─────────────────────────
  // `formatMoney` on every dashboard page reads from useJobStore.sourceCurrency
  // so values FX-convert correctly. The KPI summary endpoint conveniently
  // returns the latest completed upload's `source_currency`, so we piggyback
  // that single call rather than adding a dedicated endpoint.
  useEffect(() => {
    if (!isAuthenticated || !user?.id) return;
    kpiApi.summary()
      .then((res) => {
        const ccy = (res.data as any)?.source_currency;
        if (ccy) setSourceCurrency(ccy);
      })
      .catch(() => {
        // Best-effort — pages already default to 'USD' if hydration fails.
      });
  }, [isAuthenticated, user?.id, setSourceCurrency]);

  const handleOnboardingComplete = () => {
    if (typeof window !== 'undefined' && user?.id) {
      localStorage.setItem(`insightx_onboarded_${user.id}`, '1');
    }
    setShowOnboarding(false);
    // Hard reload to /dashboard so every page re-mounts and re-fetches with
    // the freshly-completed upload's data. Without this, pages that mounted
    // while the user had no data keep their empty-state forever until the
    // user manually refreshes.
    if (typeof window !== 'undefined') {
      window.location.href = '/dashboard';
    }
  };

  // ── Click-outside handlers for all 3 popovers ──
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(event.target as Node)) {
        setIsNotificationsOpen(false);
      }
      if (langRef.current && !langRef.current.contains(event.target as Node)) {
        setIsLangOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close mobile sidebar on route change
  useEffect(() => { setIsMobileOpen(false); }, [pathname]);

  // Helper — the nav sidebar content (shared by desktop aside + mobile drawer)
  const SidebarContent = (
    <>
      <div className="flex flex-col gap-8">
        {/* Logo */}
        <div className="flex items-center justify-between px-2 mt-2">
          <h1 className="text-gray-900 dark:text-white text-lg font-bold leading-normal tracking-tight">InsightX</h1>
          {/* Close button — visible only inside the mobile drawer */}
          <button
            onClick={() => setIsMobileOpen(false)}
            className="md:hidden p-1.5 rounded-md text-slate-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10"
            aria-label="Close menu"
          >
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Menu Items */}
        <nav className="flex flex-col gap-2">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group ${
                  isActive
                    ? 'bg-primary text-white shadow-sm'
                    : 'text-slate-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-surface-card hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <Icon className={`w-5 h-5 shrink-0 ${isActive ? 'text-white' : 'group-hover:text-gray-900 dark:group-hover:text-white'}`} />
                <p className="text-sm font-medium leading-normal">{link.name}</p>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Bottom Settings + footer links */}
      <div className="flex flex-col gap-2 border-t border-gray-200 dark:border-surface-border pt-4">
        <Link
          href="/dashboard/settings"
          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group ${
            pathname === '/dashboard/settings'
              ? 'bg-primary text-white shadow-sm'
              : 'text-slate-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-surface-card hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          <Settings className={`w-5 h-5 shrink-0 ${pathname === '/dashboard/settings' ? 'text-white' : 'group-hover:text-gray-900 dark:group-hover:text-white'}`} />
          <p className="text-sm font-medium leading-normal">{t('nav_settings', language)}</p>
        </Link>
        <div className="flex flex-col space-y-1.5 px-3 py-2 mt-2 border-t border-gray-100 dark:border-surface-border/50">
          <Link href="/support" className="text-xs text-slate-400 hover:text-primary transition-colors">{t('support', language)}</Link>
          <Link href="/terms"   className="text-xs text-slate-400 hover:text-primary transition-colors">{t('terms', language)}</Link>
          <Link href="/privacy" className="text-xs text-slate-400 hover:text-primary transition-colors">{t('privacy', language)}</Link>
        </div>
      </div>
    </>
  );

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background-light dark:bg-background-dark text-slate-900 dark:text-white font-sans">
      {/* ── Mobile sidebar backdrop overlay ─────────────────────────────────── */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={() => setIsMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── Mobile drawer sidebar ──────────────────────────────────────────── */}
      <aside
        className={`fixed inset-y-0 start-0 z-50 flex flex-col justify-between w-64 border-e border-gray-200 dark:border-surface-border bg-white dark:bg-background-dark p-4 transition-transform duration-300 md:hidden ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Mobile navigation"
      >
        {SidebarContent}
      </aside>

      {/* ── Desktop sidebar (always visible on md+) ─────────────────────────── */}
      <aside className="hidden md:flex w-64 flex-col justify-between border-e border-gray-200 dark:border-surface-border bg-white dark:bg-background-dark p-4 shrink-0">
        {SidebarContent}
      </aside>

      {/* Main Content Area */}
      <main className="flex flex-1 flex-col h-full relative overflow-y-auto custom-scrollbar">
        {/* Header.
            z-30 (was z-10): page sub-headers like /dashboard/forecasting's
            "Revenue Forecast / Export / Save Forecast" strip use
            `backdrop-blur`, which spawns its own stacking context. With both
            at z-10 the language / notifications / profile popovers would land
            BEHIND the sub-header. Bumping to z-30 keeps every popover that
            lives inside this header on top of every page-level chrome. */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-gray-200 dark:border-surface-border bg-white/95 dark:bg-background-dark/95 backdrop-blur px-4 md:px-8 py-4">
          <div className="flex items-center gap-3">
            {/* Hamburger — only visible on mobile (hidden on md+) */}
            <button
              onClick={() => setIsMobileOpen(true)}
              className="md:hidden p-2 rounded-lg text-slate-500 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
              aria-label="Open menu"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-gray-900 dark:text-white text-xl font-bold">{t('nav_dashboard', language)}</h2>
          </div>

          <div className="flex items-center gap-3 md:gap-4">
            <Link href="/dashboard/upload" className="btn btn-primary btn-sm flex items-center gap-2">
              <span className="text-lg leading-none">+</span> {t('nav_newAnalysis', language)}
            </Link>

            {/* Language picker — same UX as PublicHeader so users have one mental model */}
            <div className="relative" ref={langRef}>
              <button
                onClick={() => setIsLangOpen((o) => !o)}
                aria-label={t('language', language)}
                aria-haspopup="listbox"
                aria-expanded={isLangOpen}
                className="flex items-center gap-1.5 text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white px-2 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
              >
                <Globe size={16} strokeWidth={1.8} />
                <span className="hidden sm:inline uppercase tracking-wide text-xs font-semibold">{language}</span>
                <ChevronDown size={14} className={`transition-transform duration-200 ${isLangOpen ? 'rotate-180' : ''}`} />
              </button>
              {isLangOpen && (
                <div
                  role="listbox"
                  className="absolute end-0 mt-2 w-40 bg-white dark:bg-surface-card border border-gray-200 dark:border-surface-border rounded-xl shadow-xl overflow-hidden z-50"
                >
                  {LANGUAGES.map((lng) => (
                    <button
                      key={lng.code}
                      role="option"
                      aria-selected={language === lng.code}
                      onClick={() => { setLanguage(lng.code); setIsLangOpen(false); }}
                      className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/10 transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <span>{lng.flag}</span>
                        <span>{lng.label}</span>
                      </span>
                      {language === lng.code && <Check size={14} className="text-primary" />}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              aria-label={t('toggleTheme', language)}
              className="p-2 rounded-lg text-slate-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
            >
              {isDark
                ? <Sun  size={18} strokeWidth={1.8} className="text-amber-400" />
                : <Moon size={18} strokeWidth={1.8} />}
            </button>

            {/* Notification Bell */}
            <div className="relative" ref={notificationsRef}>
              <button
                onClick={() => setIsNotificationsOpen(!isNotificationsOpen)}
                className="relative flex items-center justify-center w-10 h-10 rounded-full hover:bg-gray-100 dark:hover:bg-surface-card text-slate-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white transition-colors"
                aria-label={t('nav_notifications', language)}
              >
                <Bell className="w-5 h-5" />
                <span className="absolute top-2.5 end-2.5 w-2 h-2 bg-red-500 rounded-full border border-white dark:border-background-dark"></span>
              </button>

              {isNotificationsOpen && (
                <div className="absolute end-0 mt-2 w-80 bg-white dark:bg-surface-card border border-gray-200 dark:border-surface-border rounded-xl shadow-lg z-50 overflow-hidden">
                  <div className="p-4 border-b border-gray-100 dark:border-surface-border">
                    <h3 className="font-semibold text-gray-900 dark:text-white">{t('nav_notifications', language)}</h3>
                  </div>
                  <div className="py-2 flex flex-col max-h-96 overflow-y-auto custom-scrollbar">
                    <div className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-background-dark/50 cursor-pointer border-s-4 border-primary transition-colors">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">{t('analytics_status_completed', language)}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* User Profile */}
            <div className="relative" ref={profileRef}>
              <button
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="flex items-center gap-3 cursor-pointer outline-none"
                aria-label={t('nav_profile', language)}
              >
                <div className="rounded-full h-10 w-10 border-2 border-gray-200 dark:border-surface-border bg-primary/20 flex items-center justify-center text-primary font-bold hover:border-primary/50 transition-colors">
                  {user?.full_name?.[0]?.toUpperCase() || 'U'}
                </div>
              </button>

              {isProfileOpen && (
                <div className="absolute end-0 mt-2 w-56 bg-white dark:bg-surface-card border border-gray-200 dark:border-surface-border rounded-xl shadow-lg z-50 overflow-hidden">
                  <div className="p-4 border-b border-gray-100 dark:border-surface-border">
                    <p className="font-medium text-gray-900 dark:text-white truncate">{user?.full_name || 'User'}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">{user?.email || ''}</p>
                  </div>
                  <div className="py-1">
                    <Link
                      href="/dashboard/settings"
                      onClick={() => setIsProfileOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-background-dark/50 hover:text-gray-900 dark:hover:text-white transition-colors"
                    >
                      <User className="w-4 h-4" />
                      <span>{t('nav_profile', language)}</span>
                    </Link>
                  </div>
                  <div className="py-1 border-t border-gray-100 dark:border-surface-border">
                    <button
                      onClick={() => { setIsProfileOpen(false); logout(); }}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>{t('logout', language)}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Dynamic Route Content */}
        {children}
      </main>

      {showOnboarding && (
        <OnboardingModal onComplete={handleOnboardingComplete} />
      )}
    </div>
  );
}
