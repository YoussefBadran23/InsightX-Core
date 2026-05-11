'use client';

import { PublicHeader } from '@/components/layout/PublicHeader';
import { PublicFooter } from '@/components/layout/PublicFooter';
import { t } from '@/lib/i18n';
import { useUiStore } from '@/stores/uiStore';

export default function SupportPage() {
  const { language } = useUiStore();
  
  return (
    <div className="min-h-screen bg-surface dark:bg-[#0f0f1a] flex flex-col font-sans text-text-primary dark:text-slate-200">
      <PublicHeader />
      <main className="flex-1 flex flex-col max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8 pt-32 pb-16 text-right" dir={language === 'ar' ? 'rtl' : 'ltr'}>
        <div className="my-auto w-full">
          <h1 className="text-4xl font-bold mb-6 text-center md:text-start">{t('helpCenterTitle', language)}</h1>
          <div className="card w-full shadow-xl p-6 sm:p-8 space-y-6">
          <section>
            <h2 className="text-2xl font-semibold mb-3 text-gray-900 dark:text-white">{t('contactUs', language)}</h2>
            <p className="text-text-secondary dark:text-slate-400 leading-relaxed">
              {t('contactUsText', language).split('support@insightx.io')[0]}
              <a href="mailto:support@insightx.io" className="text-primary hover:underline mx-1" dir="ltr">support@insightx.io</a>
              {t('contactUsText', language).split('support@insightx.io')[1] || ''}
            </p>
          </section>
          <section>
            <h2 className="text-2xl font-semibold mb-3 text-gray-900 dark:text-white">{t('faq', language)}</h2>
            <div className="space-y-4">
              <div>
                <h3 className="font-medium text-lg text-gray-900 dark:text-white">{t('faq1q', language)}</h3>
                <p className="text-text-secondary dark:text-slate-400 text-sm mt-1">{t('faq1a', language)}</p>
              </div>
              <div>
                <h3 className="font-medium text-lg text-gray-900 dark:text-white">{t('faq2q', language)}</h3>
                <p className="text-text-secondary dark:text-slate-400 text-sm mt-1">{t('faq2a', language)}</p>
              </div>
            </div>
          </section>
        </div>
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
