'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Eye, EyeOff } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { PublicHeader } from '@/components/layout/PublicHeader';
import { PublicFooter } from '@/components/layout/PublicFooter';
import { t } from '@/lib/i18n';
import { useUiStore } from '@/stores/uiStore';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  
  const { login, isLoading } = useAuthStore();
  const router = useRouter();
  const { language } = useUiStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await login(email, password);
      // Use full page reload so the middleware reads the new cookie correctly
      const params = new URLSearchParams(window.location.search);
      const from = params.get('from') || '/dashboard';
      window.location.href = from;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid email or password');
    }
  };

  return (
    <div className="relative min-h-screen w-full flex flex-col overflow-x-hidden bg-background-light dark:bg-[#0f0f1a] font-sans text-slate-900 dark:text-slate-200">
      {/* Background Layer with Image and Overlay */}
      <div className="absolute inset-0 z-0">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img 
          className="h-full w-full object-cover opacity-30" 
          alt="Dark abstract high-tech geometric network pattern with blue accents" 
          src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop"
        />
        <div className="absolute inset-0 bg-white/70 backdrop-blur-[2px]"></div>
      </div>

      {/* Global Navigation / Logo Area */}
      <PublicHeader />

      {/* Main Content - Centered Card */}
      <main className="relative z-10 flex-1 flex w-full flex-col items-center justify-center px-4 sm:px-6 pt-24 pb-12">
        <div className="w-full max-w-[440px] rounded-2xl bg-white/90 dark:bg-[#16162a]/90 backdrop-blur-md border border-gray-200 dark:border-surface-border p-8 shadow-2xl sm:p-10">
          
          {/* Headline */}
          <div className="mb-8 text-center">
            <h1 className="text-gray-900 dark:text-white text-[28px] font-bold leading-tight tracking-tight">{t('signInTitle', language)}</h1>
            <p className="mt-2 text-slate-500 dark:text-slate-400 text-sm">{t('signInDesc', language)}</p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-500 text-sm p-3 rounded-lg text-center">
                {error}
              </div>
            )}
            
            {/* Email Field */}
            <label className="flex flex-col gap-2">
              <span className="text-gray-900 dark:text-slate-200 text-sm font-medium leading-normal">{t('emailAddress', language)}</span>
              <input 
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-gray-300 dark:border-surface-border bg-white dark:bg-[#0f0f1a] h-12 px-4 text-gray-900 dark:text-white placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                placeholder="name@company.com" 
                dir="ltr"
              />
            </label>

            {/* Password Field */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-gray-900 dark:text-slate-200 text-sm font-medium leading-normal">{t('password', language)}</span>
                <Link href="/forgot-password" className="text-primary text-xs font-medium hover:text-blue-600 hover:underline transition-colors">
                  {t('forgotPassword', language)}
                </Link>
              </div>
              <div className="relative w-full">
                <input 
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 dark:border-surface-border bg-white dark:bg-[#0f0f1a] h-12 px-4 ltr:pr-12 rtl:pl-12 text-gray-900 dark:text-white placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                  placeholder="••••••••" 
                  dir="ltr"
                />
                <button 
                  type="button" 
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute rtl:left-0 ltr:right-0 top-0 h-full px-3 text-slate-400 hover:text-gray-900 dark:hover:text-white transition-colors flex items-center justify-center focus:outline-none"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* Login Button */}
            <button 
              type="submit" 
              disabled={isLoading}
              className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary py-3.5 text-base font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed outline-none transition-all duration-200"
            >
              {isLoading ? t('loggingInBtn', language) : t('logInBtn', language)}
            </button>
          </form>

          {/* Footer Link */}
          <div className="mt-8 text-center">
            <p className="text-slate-500 dark:text-slate-400 text-sm">
              {t('noAccount', language)} 
              <Link href="/signup" className="text-primary font-medium hover:text-blue-600 hover:underline transition-colors rtl:mr-1 ltr:ml-1">
                {t('signup', language)}
              </Link>
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <div className="mt-auto relative z-10 w-full">
        <PublicFooter />
      </div>
    </div>
  );
}
