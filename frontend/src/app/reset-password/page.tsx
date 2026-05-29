'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff } from 'lucide-react';
import { authApi } from '@/lib/api';

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const t = searchParams.get('token');
    if (t) setToken(t);
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setStatus('error');
      setMessage('Passwords do not match');
      return;
    }

    setStatus('loading');
    setMessage('');

    try {
      await authApi.resetPassword(token, password);
      setStatus('success');
      setMessage('Your password has been successfully reset.');
      setTimeout(() => {
        router.push('/login');
      }, 3000);
    } catch (err: any) {
      setStatus('error');
      setMessage(err.response?.data?.detail || 'Invalid or expired token. Please request a new link.');
    }
  };

  if (!token && status !== 'success') {
    return (
      <div className="text-center">
        <p className="text-red-500 mb-4">Invalid or missing reset token.</p>
        <Link href="/forgot-password" className="text-primary hover:underline">
          Request a new link
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full">
      {status === 'success' ? (
        <div className="flex flex-col items-center justify-center gap-6 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
            <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-gray-900 text-sm font-medium">{message}</p>
          <p className="text-slate-500 text-xs mt-2">Redirecting to login...</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {status === 'error' && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-500 text-sm p-3 rounded-lg text-center">
              {message}
            </div>
          )}

          <label className="flex flex-col gap-2">
            <span className="text-gray-900 text-sm font-medium">New Password</span>
            <div className="relative w-full">
              <input 
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white h-12 px-4 pr-12 text-gray-900 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all shadow-sm" 
                placeholder="Minimum 8 characters" 
              />
              <button 
                type="button" 
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-0 top-0 h-full px-3 text-slate-400 hover:text-primary transition-colors flex items-center justify-center focus:outline-none"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-gray-900 text-sm font-medium">Confirm New Password</span>
            <input 
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white h-12 px-4 text-gray-900 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all shadow-sm" 
              placeholder="Confirm password" 
            />
          </label>

          <button 
            type="submit" 
            disabled={status === 'loading'}
            className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary py-3.5 text-base font-semibold text-white shadow-lg hover:bg-primary-hover disabled:opacity-50 transition-all duration-200"
          >
            {status === 'loading' ? 'Resetting...' : 'Set New Password'}
          </button>
        </form>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="relative min-h-screen w-full flex flex-col justify-center overflow-x-hidden bg-background-light dark:bg-background-dark font-sans text-slate-900 dark:text-white">
      <div className="absolute inset-0 z-0">
        <img 
          className="h-full w-full object-cover opacity-30" 
          alt="Dark abstract high-tech background" 
          src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop"
        />
        <div className="absolute inset-0 bg-white/70 backdrop-blur-[2px]"></div>
      </div>

      <header className="absolute top-0 left-0 w-full z-20 px-8 py-6">
        <div className="flex items-center gap-3 text-gray-900">
          <h2 className="text-gray-900 text-xl font-bold leading-tight tracking-tight">InsightX</h2>
        </div>
      </header>

      <main className="relative z-10 flex w-full flex-col items-center justify-center px-4 sm:px-6">
        <div className="w-full max-w-[440px] rounded-2xl bg-white/90 backdrop-blur-md border border-gray-200 p-8 shadow-2xl sm:p-10">
          <div className="mb-8 text-center">
            <h1 className="text-gray-900 text-[28px] font-bold leading-tight tracking-tight">Create New Password</h1>
            <p className="mt-2 text-slate-500 text-sm">Please choose a strong password for your account.</p>
          </div>

          <Suspense fallback={<div className="text-center py-8">Loading...</div>}>
            <ResetPasswordForm />
          </Suspense>

          <div className="mt-8 text-center">
            <Link href="/login" className="text-primary text-sm font-medium hover:underline transition-colors">
              Back to Login
            </Link>
          </div>
        </div>
      </main>

      <footer className="absolute bottom-6 w-full text-center z-10 px-4">
        <p className="text-slate-500 text-xs shadow-sm">© 2026 InsightX Inc. All rights reserved.</p>
      </footer>
    </div>
  );
}
