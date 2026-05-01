'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Eye, EyeOff, Building2, ArrowRight } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { PublicHeader } from '@/components/layout/PublicHeader';
import { PublicFooter } from '@/components/layout/PublicFooter';
import { t } from '@/lib/i18n';
import { useUiStore } from '@/stores/uiStore';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  
  const { register, isLoading } = useAuthStore();
  const router = useRouter();
  const { language } = useUiStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    try {
      await register(email, password, fullName);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create account');
    }
  };

  return (
    <div className="bg-background-light dark:bg-[#0f0f1a] text-slate-900 dark:text-slate-200 min-h-screen flex flex-col font-sans overflow-x-hidden">
      {/* Background Layer with Overlay */}
      <div className="fixed inset-0 z-0">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img 
          className="absolute inset-0 bg-cover bg-center h-full w-full object-cover opacity-30" 
          alt="Abstract dark blue cyber technology background" 
          src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop"
        />
        <div className="absolute inset-0 bg-white/80 backdrop-blur-[2px]"></div>
      </div>

      {/* Content Layer */}
      <div className="relative z-10 flex flex-col h-full min-h-screen">
        <PublicHeader />

        {/* Main Content Area */}
        <main className="flex-1 flex items-center justify-center p-4 pt-24 pb-12">
          <div className="w-full max-w-[540px] flex flex-col">
            
            {/* Auth Card */}
            <div className="bg-white/90 dark:bg-[#16162a]/90 backdrop-blur-md border border-gray-200 dark:border-surface-border rounded-xl shadow-2xl p-6 md:p-10 w-full relative overflow-hidden">
              {/* Subtle gradient glow at top of card */}
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-primary/50 to-transparent"></div>
              
              <div className="mb-8 text-center md:rtl:text-right md:ltr:text-left">
                <h1 className="text-gray-900 dark:text-white tracking-tight text-3xl font-bold leading-tight mb-2">{t('createAccountTitle', language)}</h1>
                <p className="text-slate-500 dark:text-slate-400 text-sm">{t('createAccountDesc', language)}</p>
              </div>

              <form onSubmit={handleSubmit} className="flex flex-col gap-5">
                {error && (
                  <div className="bg-red-500/10 border border-red-500/20 text-red-500 text-sm p-3 rounded-lg text-center">
                    {error}
                  </div>
                )}

                {/* Full Name */}
                <div className="flex flex-col gap-2">
                  <label className="text-gray-900 dark:text-slate-200 text-sm font-medium leading-normal">{t('fullName', language)}</label>
                  <div className="relative flex w-full items-center">
                    <div className="absolute ltr:left-0 rtl:right-0 top-0 bottom-0 flex items-center ltr:pl-4 rtl:pr-4 pointer-events-none text-slate-400">
                      <Building2 className="w-5 h-5" />
                    </div>
                    <input 
                      type="text"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full rounded-lg border border-gray-300 dark:border-surface-border bg-white dark:bg-[#0f0f1a] h-12 ltr:pl-11 rtl:pr-11 ltr:pr-4 rtl:pl-4 text-gray-900 dark:text-white placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                      placeholder="Acme Corp" 
                    />
                  </div>
                </div>

                {/* Work Email */}
                <div className="flex flex-col gap-2">
                  <label className="text-gray-900 dark:text-slate-200 text-sm font-medium leading-normal">{t('workEmail', language)}</label>
                  <input 
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 dark:border-surface-border bg-white dark:bg-[#0f0f1a] h-12 px-4 text-gray-900 dark:text-white placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                    placeholder="name@company.com" 
                    dir="ltr"
                  />
                </div>

                {/* Password */}
                <div className="flex flex-col gap-2">
                  <label className="text-gray-900 dark:text-slate-200 text-sm font-medium leading-normal">{t('password', language)}</label>
                  <div className="relative flex w-full items-center">
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
                      className="absolute ltr:right-0 rtl:left-0 top-0 bottom-0 flex items-center justify-center px-4 cursor-pointer text-slate-400 hover:text-gray-900 dark:hover:text-white transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                {/* Confirm Password */}
                <div className="flex flex-col gap-2">
                  <label className="text-gray-900 dark:text-slate-200 text-sm font-medium leading-normal">{t('confirmPassword', language)}</label>
                  <div className="relative flex w-full items-center">
                    <input 
                      type={showPassword ? "text" : "password"}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full rounded-lg border border-gray-300 dark:border-surface-border bg-white dark:bg-[#0f0f1a] h-12 px-4 ltr:pr-12 rtl:pl-12 text-gray-900 dark:text-white placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                      placeholder="••••••••" 
                      dir="ltr"
                    />
                  </div>
                </div>

                {/* Submit Button */}
                <div className="pt-2">
                  <button 
                    type="submit" 
                    disabled={isLoading}
                    className="w-full bg-primary hover:bg-primary-hover text-white font-bold h-12 rounded-lg shadow-lg shadow-primary/20 transition-all duration-200 transform active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2 outline-none"
                  >
                    <span>{isLoading ? t('signingUpBtn', language) : t('signUpBtn', language)}</span>
                    {!isLoading && <ArrowRight className="w-5 h-5 rtl:rotate-180" />}
                  </button>
                </div>

                {/* Footer Link */}
                <div className="text-center mt-2">
                  <p className="text-slate-500 dark:text-slate-400 text-sm">
                    {t('haveAccount', language)} 
                    <Link href="/login" className="text-primary hover:text-blue-600 font-medium transition-colors hover:underline ltr:ml-1 rtl:mr-1">
                      {t('login', language)}
                    </Link>
                  </p>
                </div>
              </form>
            </div>
          </div>
        </main>
        
        <PublicFooter />
      </div>
    </div>
  );
}
