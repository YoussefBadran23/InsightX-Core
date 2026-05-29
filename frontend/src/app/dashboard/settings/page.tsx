'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  LogOut, Settings as SettingsIcon, Sun, Moon, Globe, DollarSign,
  Building2, Upload, Save, Check, X, AlertCircle, Loader2,
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { authApi } from '@/lib/api';
import { t, type Locale } from '@/lib/i18n';

// ISO 4217 list — keep short, common currencies that matter for the demo audience.
const CURRENCIES: { code: string; label: string; symbol: string }[] = [
  { code: 'USD', label: 'US Dollar',         symbol: '$' },
  { code: 'EUR', label: 'Euro',              symbol: '€' },
  { code: 'GBP', label: 'British Pound',     symbol: '£' },
  { code: 'SAR', label: 'Saudi Riyal',       symbol: 'ر.س' },
  { code: 'AED', label: 'UAE Dirham',        symbol: 'د.إ' },
  { code: 'EGP', label: 'Egyptian Pound',    symbol: 'ج.م' },
  { code: 'KWD', label: 'Kuwaiti Dinar',     symbol: 'د.ك' },
  { code: 'QAR', label: 'Qatari Riyal',      symbol: 'ر.ق' },
  { code: 'BHD', label: 'Bahraini Dinar',    symbol: 'د.ب' },
  { code: 'OMR', label: 'Omani Rial',        symbol: 'ر.ع' },
  { code: 'JOD', label: 'Jordanian Dinar',   symbol: 'د.أ' },
  { code: 'TRY', label: 'Turkish Lira',      symbol: '₺' },
  { code: 'BRL', label: 'Brazilian Real',    symbol: 'R$' },
  { code: 'JPY', label: 'Japanese Yen',      symbol: '¥' },
  { code: 'CNY', label: 'Chinese Yuan',      symbol: '¥' },
];

const LANGUAGES: { code: Locale; label: string; flag: string }[] = [
  { code: 'en', label: 'English',  flag: '🇬🇧' },
  { code: 'ar', label: 'العربية',  flag: '🇸🇦' },
];

const MAX_LOGO_BYTES = 1_500_000; // 1.5 MB raw file — base64 inflates ~33%

export default function SettingsPage() {
  const router = useRouter();
  const { user, logout, fetchMe } = useAuthStore();
  const { theme, language, toggleTheme, setLanguage } = useUiStore();

  // ── Local form state ──
  const [companyName, setCompanyName] = useState('');
  const [logoDataUrl, setLogoDataUrl] = useState<string | null>(null);
  const [currency, setCurrency] = useState('USD');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Hydrate from current user on mount + whenever user changes ──
  useEffect(() => {
    if (!user) return;
    setCompanyName(user.company_name || '');
    setLogoDataUrl(user.company_logo_url || null);
    setCurrency(user.preferred_currency || 'USD');
  }, [user]);

  // ── Logo upload (file → base64 data URL stored in state) ──
  const handleLogoFile = (file: File) => {
    setError(null);
    if (!file.type.startsWith('image/')) {
      setError(t('settings_logoMustBeImage', language) || 'Logo must be an image file (PNG, JPG, SVG).');
      return;
    }
    if (file.size > MAX_LOGO_BYTES) {
      setError(`${t('settings_logoTooLarge', language) || 'Logo too large'} — ${(file.size / 1024 / 1024).toFixed(1)}MB. Max 1.5 MB.`);
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => setLogoDataUrl(String(e.target?.result || ''));
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await authApi.updateMe({
        company_name: companyName || undefined,
        company_logo_url: logoDataUrl, // null clears it, data URL replaces it
        preferred_currency: currency,
        preferred_language: language,
      });
      await fetchMe(); // refresh cached user
      setSavedAt(Date.now());
      setTimeout(() => setSavedAt(null), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to save settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  if (!user) {
    return (
      <div className="p-8 flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 animate-fade-in">
      <div className="mx-auto max-w-4xl flex flex-col gap-6">
        {/* Header */}
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">
            {t('settings_title', language)}
          </h1>
          <p className="text-slate-500 dark:text-slate-400">
            {t('settings_manageAccountPrefs', language) || 'Manage your account and preferences.'}
          </p>
        </div>

        {/* Profile card (read-only display) */}
        <section className="bg-white dark:bg-surface-card rounded-xl shadow-sm border border-gray-200 dark:border-surface-border overflow-hidden">
          <div className="p-6 border-b border-gray-200 dark:border-surface-border flex items-center gap-4">
            <div className="w-16 h-16 bg-primary/10 text-primary rounded-full flex items-center justify-center font-bold text-2xl border-2 border-primary/20 shrink-0">
              {user.full_name?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="min-w-0">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white truncate">{user.full_name || 'System User'}</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 truncate">{user.email}</p>
              <span className="mt-1 inline-block text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 uppercase font-semibold tracking-wider">
                {user.role}
              </span>
            </div>
          </div>
        </section>

        {/* Company section — logo + name */}
        <section className="bg-white dark:bg-surface-card rounded-xl shadow-sm border border-gray-200 dark:border-surface-border overflow-hidden">
          <div className="p-6 border-b border-gray-200 dark:border-surface-border">
            <h3 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
              <Building2 className="w-4 h-4" />
              {t('settings_company', language) || 'Company'}
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {t('settings_companyDesc', language) || 'These appear on uploaded reports and the dashboard header.'}
            </p>
          </div>

          <div className="p-6 flex flex-col md:flex-row gap-6">
            {/* Logo preview + upload */}
            <div className="shrink-0">
              <div className="w-32 h-32 rounded-xl border-2 border-dashed border-gray-300 dark:border-surface-border bg-gray-50 dark:bg-background-dark/50 flex items-center justify-center overflow-hidden">
                {logoDataUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={logoDataUrl} alt="logo preview" className="w-full h-full object-contain p-2" />
                ) : (
                  <div className="text-center text-slate-400 text-xs px-2">
                    <Upload className="w-6 h-6 mx-auto mb-2" />
                    {t('settings_noLogo', language) || 'No logo yet'}
                  </div>
                )}
              </div>
              <div className="flex gap-2 mt-3">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-1 text-xs px-3 py-1.5 rounded-md bg-primary hover:bg-primary-hover text-white font-medium transition-colors"
                >
                  {logoDataUrl
                    ? (t('settings_changeLogo', language) || 'Change')
                    : (t('settings_uploadLogo', language) || 'Upload')}
                </button>
                {logoDataUrl && (
                  <button
                    type="button"
                    onClick={() => setLogoDataUrl(null)}
                    className="px-2 py-1.5 rounded-md text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                    aria-label="Remove logo"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleLogoFile(f);
                  e.target.value = ''; // allow re-selecting same file
                }}
              />
              <p className="text-[10px] text-slate-400 mt-2 text-center">PNG · JPG · SVG · max 1.5MB</p>
            </div>

            {/* Company name field */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-200 mb-2">
                {t('settings_companyName', language) || 'Company name'}
              </label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder={t('settings_companyNamePlaceholder', language) || 'Acme Inc.'}
                maxLength={255}
                className="w-full px-4 py-2.5 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg text-gray-900 dark:text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none placeholder-slate-400"
              />
            </div>
          </div>
        </section>

        {/* Preferences section — language + currency + theme */}
        <section className="bg-white dark:bg-surface-card rounded-xl shadow-sm border border-gray-200 dark:border-surface-border overflow-hidden">
          <div className="p-6 border-b border-gray-200 dark:border-surface-border">
            <h3 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
              <SettingsIcon className="w-4 h-4" />
              {t('settings_preferences', language) || 'Preferences'}
            </h3>
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Language */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-200 mb-2 flex items-center gap-2">
                <Globe className="w-4 h-4" /> {t('settings_languageLabel', language)}
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value as Locale)}
                className="w-full px-4 py-2.5 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg text-gray-900 dark:text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none"
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>{l.flag} {l.label}</option>
                ))}
              </select>
              <p className="text-[11px] text-slate-400 mt-1">{t('settings_languageHint', language) || 'Changes apply immediately'}</p>
            </div>

            {/* Currency */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-200 mb-2 flex items-center gap-2">
                <DollarSign className="w-4 h-4" /> {t('settings_currency', language) || 'Currency'}
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg text-gray-900 dark:text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none"
              >
                {CURRENCIES.map((c) => (
                  <option key={c.code} value={c.code}>{c.code} — {c.label} ({c.symbol})</option>
                ))}
              </select>
              <p className="text-[11px] text-slate-400 mt-1">{t('settings_currencyHint', language) || 'Used to format money throughout the app'}</p>
            </div>

            {/* Theme */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-200 mb-2 flex items-center gap-2">
                {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                {t('settings_theme', language)}
              </label>
              <button
                onClick={toggleTheme}
                className="w-full px-4 py-2.5 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg text-gray-900 dark:text-white text-sm hover:bg-gray-100 dark:hover:bg-surface-hover transition-colors flex items-center justify-between"
              >
                <span>{theme === 'dark' ? t('settings_themeDark', language) : t('settings_themeLight', language)}</span>
                {theme === 'dark'
                  ? <Sun  size={16} className="text-amber-400" />
                  : <Moon size={16} className="text-slate-500" />}
              </button>
              <p className="text-[11px] text-slate-400 mt-1">{t('settings_themeHint', language) || 'Persists across sessions'}</p>
            </div>
          </div>
        </section>

        {/* Save bar */}
        <section className="bg-white dark:bg-surface-card rounded-xl shadow-sm border border-gray-200 dark:border-surface-border p-4 flex items-center justify-between gap-4">
          <div className="text-sm">
            {error && (
              <span className="text-red-600 dark:text-red-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" /> {error}
              </span>
            )}
            {savedAt && !error && (
              <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                <Check className="w-4 h-4 shrink-0" /> {t('settings_saved', language) || 'Saved'}
              </span>
            )}
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-primary hover:bg-primary-hover disabled:opacity-50 text-white rounded-lg font-medium text-sm shadow-md transition-all"
          >
            {saving
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Save className="w-4 h-4" />}
            {saving ? (t('settings_saving', language) || 'Saving...') : (t('settings_save', language) || 'Save changes')}
          </button>
        </section>

        {/* Account actions */}
        <section className="bg-white dark:bg-surface-card rounded-xl shadow-sm border border-gray-200 dark:border-surface-border overflow-hidden">
          <div className="p-6">
            <h3 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider mb-4 flex items-center gap-2">
              <SettingsIcon className="w-4 h-4" />
              {t('settings_accountActions', language) || 'Account Actions'}
            </h3>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-500/20 hover:bg-red-100 dark:hover:bg-red-500/20 rounded-lg transition-colors font-medium text-sm"
            >
              <LogOut className="w-4 h-4" />
              {t('settings_signOut', language)}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
