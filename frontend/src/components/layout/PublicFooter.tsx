'use client';

import Link from 'next/link';
import { useUiStore } from '@/stores/uiStore';
import { t } from '@/lib/i18n';

export function PublicFooter() {
  const { language } = useUiStore();

  return (
    <footer className="glass border-t border-gray-200 dark:border-white/5 transition-colors duration-300 relative z-30 mt-auto">
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
          <div className="flex gap-8">
            <Link className="text-sm text-slate-500 dark:text-slate-400 hover:text-primary dark:hover:text-primary transition-colors" href="/support">{t('support', language)}</Link>
            <Link className="text-sm text-slate-500 dark:text-slate-400 hover:text-primary dark:hover:text-primary transition-colors" href="/terms">{t('terms', language)}</Link>
            <Link className="text-sm text-slate-500 dark:text-slate-400 hover:text-primary dark:hover:text-primary transition-colors" href="/privacy">{t('privacy', language)}</Link>
          </div>
        </div>
        <div className="mt-4 text-center text-xs text-gray-400 dark:text-gray-500">
          {t('footer', language)}
        </div>
      </div>
    </footer>
  );
}
