'use client';

import { useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { PublicHeader } from '@/components/layout/PublicHeader';
import { PublicFooter } from '@/components/layout/PublicFooter';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('loading');
    setMessage('');
    
    try {
      await api.post('/auth/forgot-password', { email });
      // Always show success to prevent email enumeration, matching the backend logic
      setStatus('success');
      setMessage('If an account exists for that email, a password reset link has been sent.');
    } catch (err: any) {
      setStatus('error');
      setMessage(err.response?.data?.detail || 'An unexpected error occurred. Please try again.');
    }
  };

  return (
    <div className="relative min-h-screen w-full flex flex-col overflow-x-hidden bg-background-light dark:bg-[#0f0f1a] font-sans text-slate-900 dark:text-slate-200">
      {/* Background Layer with Image and Overlay */}
      <div className="absolute inset-0 z-0">
        <div className="absolute inset-0 bg-white/90 dark:bg-[#0f0f1a]/80 z-10" />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          alt="Abstract connectivity network background"
          className="w-full h-full object-cover"
          src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop"
        />
      </div>

      {/* Global Navigation / Logo Area */}
      <PublicHeader />

      {/* Main Content - Centered Card */}
      <main className="relative z-10 flex-1 flex w-full flex-col items-center justify-center px-4 sm:px-6 pt-24 pb-12">
        <div className="w-full max-w-[440px] rounded-2xl bg-white/90 dark:bg-[#16162a]/90 backdrop-blur-md border border-gray-200 dark:border-white/5 p-8 shadow-2xl sm:p-10">
          
          {/* Headline */}
          <div className="mb-8 text-center">
            <h1 className="text-gray-900 dark:text-white text-[28px] font-bold leading-tight tracking-tight">Reset Password</h1>
            <p className="mt-2 text-slate-500 dark:text-slate-400 text-sm">Enter your email and we'll send you a link to reset your password.</p>
          </div>

          {status === 'success' ? (
            <div className="flex flex-col items-center justify-center gap-6 text-center">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900/50 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <p className="text-gray-900 dark:text-white text-sm font-medium">{message}</p>
              <Link 
                href="/login" 
                className="mt-4 flex w-full items-center justify-center rounded-lg bg-primary py-3.5 text-base font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary-hover transition-all duration-200"
              >
                Return to Login
              </Link>
            </div>
          ) : (
            /* Forgot Password Form */
            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              {status === 'error' && (
                <div className="bg-red-500/10 border border-red-500/20 text-red-500 text-sm p-3 rounded-lg text-center">
                  {message}
                </div>
              )}
              
              {/* Email Field */}
              <label className="flex flex-col gap-2">
                <span className="text-gray-900 dark:text-slate-200 text-sm font-medium leading-normal">Email Address</span>
                <input 
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-[#0f0f1a] h-12 px-4 text-gray-900 dark:text-white placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                  placeholder="name@company.com" 
                />
              </label>

              {/* Submit Button */}
              <button 
                type="submit" 
                disabled={status === 'loading'}
                className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary py-3.5 text-base font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed outline-none transition-all duration-200"
              >
                {status === 'loading' ? 'Sending Link...' : 'Send Reset Link'}
              </button>
            </form>
          )}

          {/* Footer Link */}
          {status !== 'success' && (
            <div className="mt-8 text-center">
              <Link href="/login" className="text-primary text-sm font-medium hover:text-blue-600 hover:underline transition-colors flex items-center justify-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Back to Login
              </Link>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <div className="mt-auto relative z-10 w-full">
        <PublicFooter />
      </div>
    </div>
  );
}
