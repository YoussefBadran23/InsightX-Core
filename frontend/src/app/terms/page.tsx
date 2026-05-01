'use client';

import { PublicHeader } from '@/components/layout/PublicHeader';
import { PublicFooter } from '@/components/layout/PublicFooter';
import { t } from '@/lib/i18n';
import { useUiStore } from '@/stores/uiStore';

export default function TermsPage() {
  const { language } = useUiStore();
  
  return (
    <div className="min-h-screen bg-surface dark:bg-[#0f0f1a] flex flex-col font-sans text-text-primary dark:text-slate-200">
      <PublicHeader />
      <main className="flex-1 max-w-4xl mx-auto w-full p-8 md:p-16 text-right" dir={language === 'ar' ? 'rtl' : 'ltr'}>
        <h1 className="text-4xl font-bold mb-6 text-center md:text-start">{t('termsTitle', language)}</h1>
        <div className="bg-white dark:bg-[#16162a] rounded-xl shadow-lg border border-gray-200 dark:border-surface-border p-8 space-y-6">
          <p className="text-sm text-text-muted dark:text-slate-500">{t('lastUpdatedTerms', language)}</p>
          <section>
            <h2 className="text-2xl font-semibold mb-3 text-gray-900 dark:text-white">{t('terms1Title', language)}</h2>
            <p className="text-text-secondary dark:text-slate-400 leading-relaxed">
              {t('terms1Text', language)}
            </p>
          </section>
          <section>
            <h2 className="text-2xl font-semibold mb-3 text-gray-900 dark:text-white">{t('terms2Title', language)}</h2>
            <p className="text-text-secondary dark:text-slate-400 leading-relaxed">
              {t('terms2Text', language)}
            </p>
          </section>
          <section>
            <h2 className="text-2xl font-semibold mb-3 text-gray-900 dark:text-white">{t('terms3Title', language)}</h2>
            <p className="text-text-secondary dark:text-slate-400 leading-relaxed">
              {t('terms3Text', language)}
            </p>
          </section>
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
