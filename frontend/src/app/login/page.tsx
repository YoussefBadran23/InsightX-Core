'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Eye, EyeOff } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  
  const { login, isLoading } = useAuthStore();
  const router = useRouter();

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
    <div className="relative min-h-screen w-full flex flex-col justify-center overflow-x-hidden bg-background-light dark:bg-background-dark font-sans text-slate-900 dark:text-white">
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
      <header className="absolute top-0 left-0 w-full z-20 px-8 py-6">
        <div className="flex items-center gap-3 text-gray-900">
          <h2 className="text-gray-900 text-xl font-bold leading-tight tracking-tight">InsightX</h2>
        </div>
      </header>

      {/* Main Content - Centered Card */}
      <main className="relative z-10 flex w-full flex-col items-center justify-center px-4 sm:px-6">
        <div className="w-full max-w-[440px] rounded-2xl bg-white/90 backdrop-blur-md border border-gray-200 p-8 shadow-2xl sm:p-10">
          
          {/* Headline */}
          <div className="mb-8 text-center">
            <h1 className="text-gray-900 text-[28px] font-bold leading-tight tracking-tight">Sign In to InsightX</h1>
            <p className="mt-2 text-slate-500 text-sm">Secure access to your dashboard</p>
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
              <span className="text-gray-900 text-sm font-medium leading-normal">Email Address</span>
              <input 
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white h-12 px-4 text-gray-900 placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                placeholder="name@company.com" 
              />
            </label>

            {/* Password Field */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-gray-900 text-sm font-medium leading-normal">Password</span>
                <Link href="/forgot-password" className="text-primary text-xs font-medium hover:text-blue-600 hover:underline transition-colors">
                  Forgot password?
                </Link>
              </div>
              <div className="relative w-full">
                <input 
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white h-12 px-4 pr-12 text-gray-900 placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                  placeholder="Enter your password" 
                />
                <button 
                  type="button" 
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-0 top-0 h-full px-3 text-slate-400 hover:text-white transition-colors flex items-center justify-center focus:outline-none"
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
              {isLoading ? 'Logging In...' : 'Log In'}
            </button>
          </form>

          {/* Footer Link */}
          <div className="mt-8 text-center">
            <p className="text-slate-500 text-sm">
              Don't have an account? 
              <Link href="/signup" className="text-primary font-medium hover:text-blue-600 hover:underline transition-colors ml-1">
                Sign Up
              </Link>
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="absolute bottom-6 w-full text-center z-10 px-4">
        <p className="text-slate-500 text-xs shadow-sm">© 2026 InsightX Inc. All rights reserved.</p>
      </footer>
    </div>
  );
}
