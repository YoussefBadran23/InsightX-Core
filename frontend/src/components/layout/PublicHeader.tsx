'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, useRef, useEffect } from 'react';
import { Sun, Moon, Globe, ChevronDown, Check } from 'lucide-react';

import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { t, type Locale } from '@/lib/i18n';

const LANGUAGES: { code: Locale; label: string; flag: string }[] = [
  { code: 'en', label: 'English', flag: '🇬🇧' },
  { code: 'ar', label: 'العربية',  flag: '🇸🇦' },
];

export function PublicHeader() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const { theme, toggleTheme, language, setLanguage } = useUiStore();

  const [langOpen, setLangOpen] = useState(false);
  const langRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (langRef.current && !langRef.current.contains(e.target as Node)) {
        setLangOpen(false);
      }
    }
    document.addEventListener('mousedown', onOutside);
    return () => document.removeEventListener('mousedown', onOutside);
  }, []);

  const logoHref = isAuthenticated ? '/dashboard' : '/';
  const isDark = theme === 'dark';

  return (
    <header className="fixed w-full top-0 z-50 glass border-b border-gray-200 dark:border-surface-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-20">
          <Link href={logoHref} className="flex items-center space-x-2 group">
            <span className="font-bold text-2xl tracking-tight text-gray-900 dark:text-white transition-opacity group-hover:opacity-80">
              Insight<span className="text-primary">X</span>
            </span>
          </Link>

          <div className="flex items-center space-x-2 sm:space-x-3">
            <div className="relative" ref={langRef}>
              <button
                id="lang-selector-btn"
                onClick={() => setLangOpen((o) => !o)}
                aria-label={t('language', language)}
                aria-haspopup="listbox"
                aria-expanded={langOpen}
                className="flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white transition-colors px-2 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-white/10"
              >
                <Globe size={16} strokeWidth={1.8} />
                <span className="hidden sm:inline uppercase tracking-wide text-xs font-semibold">
                  {language}
                </span>
                <ChevronDown
                  size={14}
                  className={`transition-transform duration-200 ${langOpen ? 'rotate-180' : ''}`}
                />
              </button>

              {langOpen && (
                <div
                  role="listbox"
                  className="absolute right-0 mt-2 w-40 glass-card border border-gray-200 dark:border-surface-border rounded-xl shadow-xl overflow-hidden origin-top-right z-50"
                >
                  {LANGUAGES.map((lng) => (
                    <button
                      key={lng.code}
                      role="option"
                      aria-selected={language === lng.code}
                      onClick={() => { setLanguage(lng.code); setLangOpen(false); }}
                      className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/10 transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <span>{lng.flag}</span>
                        <span>{lng.label}</span>
                      </span>
                      {language === lng.code && (
                        <Check size={14} className="text-primary" />
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              id="theme-toggle-btn"
              onClick={toggleTheme}
              aria-label={t('toggleTheme', language)}
              className="p-2 rounded-lg text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/10 transition-all"
            >
              {isDark
                ? <Sun size={18} strokeWidth={1.8} className="text-amber-400" />
                : <Moon size={18} strokeWidth={1.8} />
              }
            </button>

            {isAuthenticated ? (
              <Link
                href="/dashboard"
                className="bg-primary hover:bg-primary-hover text-white text-sm font-medium py-2 px-5 rounded-full transition-all shadow-lg shadow-primary/30"
              >
                {t('viewDashboard', language)}
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="text-sm font-medium text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white transition-colors"
                >
                  {t('login', language)}
                </Link>
                <Link
                  href="/signup"
                  className="bg-primary hover:bg-primary-hover text-white text-sm font-medium py-2 px-5 rounded-full transition-all shadow-lg shadow-primary/30"
                >
                  {t('signup', language)}
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
