'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, useRef, useEffect } from 'react';
import { Sun, Moon, Globe, ChevronDown, Check } from 'lucide-react';

import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { t } from '@/lib/i18n';
import { PublicHeader } from '@/components/layout/PublicHeader';
import { PublicFooter } from '@/components/layout/PublicFooter';

export default function LandingPage() {
  const router         = useRouter();
  const { isAuthenticated }       = useAuthStore();
  const { language } = useUiStore();

  /** "View Dashboard" CTA: authenticated → /dashboard, else → /login */
  const dashboardHref = isAuthenticated ? '/dashboard' : '/login';

  return (
    <div className="bg-background-light dark:bg-[#0f0f1a] text-slate-800 dark:text-slate-200 font-sans transition-colors duration-300 min-h-screen flex flex-col">

      <PublicHeader />

      {/* ── Hero ───────────────────────────────────────────────────────────── */}
      <main className="flex-grow flex items-center relative overflow-hidden pt-20">
        {/* Background */}
        <div className="absolute inset-0 z-0">
          <div className="absolute inset-0 bg-white/90 dark:bg-[#0f0f1a]/80 z-10" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            alt="Abstract connectivity network background"
            className="w-full h-full object-cover"
            src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop"
          />
        </div>

        {/* Ambient blobs */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 z-0 animate-pulse-slow" />
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-96 h-96 bg-primary rounded-full mix-blend-multiply filter blur-3xl opacity-20 z-0 animate-pulse-slow" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-20 w-full py-12 lg:py-24">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">

            {/* Left Column */}
            <div className="lg:col-span-6 flex flex-col justify-center text-center lg:text-left space-y-8">
              <div className="space-y-4">
                <h1 className="font-bold text-5xl lg:text-7xl leading-tight text-gray-900 dark:text-white">
                  {t('tagline', language)} <br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-purple-500 to-pink-500">
                    {t('tagline2', language)}
                  </span>
                </h1>
                <p className="text-lg text-slate-600 dark:text-slate-400 max-w-lg mx-auto lg:mx-0 font-light leading-relaxed">
                  {t('description', language)}
                </p>
              </div>

              {/* CTA Buttons */}
              <div className="flex flex-col sm:flex-row items-center gap-4 justify-center lg:justify-start">
                <Link
                  href="/signup"
                  id="cta-start-free-btn"
                  className="w-full sm:w-auto bg-primary hover:bg-primary-hover text-white font-semibold py-4 px-8 rounded-lg shadow-xl shadow-primary/20 transition-all transform hover:-translate-y-0.5 flex items-center justify-center space-x-2"
                >
                  <span>{t('startFree', language)}</span>
                  <span>→</span>
                </Link>

                {/* "View Dashboard" → /dashboard if authed, /login otherwise */}
                <button
                  id="cta-view-dashboard-btn"
                  onClick={() => router.push(dashboardHref)}
                  className="w-full sm:w-auto bg-transparent border border-gray-300 dark:border-surface-border hover:bg-gray-100 dark:hover:bg-surface-elevated text-gray-900 dark:text-white font-medium py-4 px-8 rounded-lg transition-all flex items-center justify-center space-x-2"
                >
                  <span>{t('viewDashboard', language)}</span>
                </button>
              </div>

              <div className="pt-2 flex items-center justify-center lg:justify-start space-x-6 text-sm text-slate-500 dark:text-slate-400">
                <div className="flex items-center space-x-2">
                  <span className="text-emerald-500 text-base">✓</span>
                  <span>{t('noCard', language)}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-emerald-500 text-base">✓</span>
                  <span>{t('freeTrial', language)}</span>
                </div>
              </div>
            </div>

            {/* Right Column: Feature Grid */}
            <div className="lg:col-span-6 relative">
              <div className="absolute inset-0 bg-gradient-to-tr from-primary/20 to-purple-500/20 rounded-full filter blur-3xl opacity-30" />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 relative">

                <div className="glass-card bg-white/90 dark:bg-[#16162a]/90 p-6 border dark:border-white/5 hover:bg-white/50 dark:hover:border-primary/30 transition-all cursor-pointer group">
                  <div className="h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center mb-4 text-blue-600 dark:text-blue-400">
                    <span className="text-2xl">☁️</span>
                  </div>
                  <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1">{t('featureStart', language)}</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{t('featureStartDesc', language)}</p>
                </div>

                <div className="glass-card bg-white/90 dark:bg-[#16162a]/90 p-6 border dark:border-white/5 hover:bg-white/50 dark:hover:border-primary/30 transition-all cursor-pointer group mt-0 sm:mt-8">
                  <div className="h-12 w-12 rounded-lg bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center mb-4 text-indigo-600 dark:text-indigo-400">
                    <span className="text-2xl">📊</span>
                  </div>
                  <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1">{t('featureAnalytics', language)}</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{t('featureAnalyticsDesc', language)}</p>
                </div>

                <div className="glass-card bg-white/90 dark:bg-[#16162a]/90 p-6 border dark:border-white/5 hover:bg-white/50 dark:hover:border-primary/30 transition-all cursor-pointer group">
                  <div className="h-12 w-12 rounded-lg bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center mb-4 text-purple-600 dark:text-purple-400">
                    <span className="text-2xl">🔮</span>
                  </div>
                  <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1">{t('featureForecasting', language)}</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{t('featureForecastingDesc', language)}</p>
                </div>

                <div className="glass-card bg-white/90 dark:bg-[#16162a]/90 p-6 border dark:border-white/5 hover:bg-white/50 dark:hover:border-primary/30 transition-all cursor-pointer group mt-0 sm:mt-8">
                  <div className="h-12 w-12 rounded-lg bg-pink-100 dark:bg-pink-900/50 flex items-center justify-center mb-4 text-pink-600 dark:text-pink-400">
                    <span className="text-2xl">🎯</span>
                  </div>
                  <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1">{t('featureSegmentation', language)}</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{t('featureSegmentationDesc', language)}</p>
                </div>

              </div>
            </div>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
