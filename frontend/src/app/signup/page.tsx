'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Eye, EyeOff, Building2, ArrowRight } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useRouter } from 'next/navigation';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  
  const { register, isLoading } = useAuthStore();
  const router = useRouter();

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
    <div className="bg-background-light dark:bg-background-dark text-slate-900 dark:text-white min-h-screen flex flex-col font-sans overflow-x-hidden">
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
        {/* Header */}
        <header className="flex items-center justify-between whitespace-nowrap px-6 py-4 lg:px-10">
          <div className="flex items-center gap-3 text-gray-900">
            <h2 className="text-gray-900 text-xl font-bold leading-tight tracking-[-0.015em]">InsightX</h2>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 flex items-center justify-center p-4">
          <div className="w-full max-w-[540px] flex flex-col">
            
            {/* Auth Card */}
            <div className="bg-white/90 backdrop-blur-md border border-gray-200 rounded-xl shadow-2xl p-6 md:p-10 w-full relative overflow-hidden">
              {/* Subtle gradient glow at top of card */}
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-primary/50 to-transparent"></div>
              
              <div className="mb-8 text-center md:text-left">
                <h1 className="text-gray-900 tracking-tight text-3xl font-bold leading-tight mb-2">Create Your InsightX Account</h1>
                <p className="text-slate-500 text-sm">Join thousands of companies using InsightX for data analytics.</p>
              </div>

              <form onSubmit={handleSubmit} className="flex flex-col gap-5">
                {error && (
                  <div className="bg-red-500/10 border border-red-500/20 text-red-500 text-sm p-3 rounded-lg text-center">
                    {error}
                  </div>
                )}

                {/* Full Name */}
                <div className="flex flex-col gap-2">
                  <label className="text-gray-900 text-sm font-medium leading-normal">Full Name / Company</label>
                  <div className="relative flex w-full items-center">
                    <div className="absolute left-0 top-0 bottom-0 flex items-center pl-4 pointer-events-none text-slate-400">
                      <Building2 className="w-5 h-5" />
                    </div>
                    <input 
                      type="text"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full rounded-lg border border-gray-300 bg-white h-12 pl-11 pr-4 text-gray-900 placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                      placeholder="Acme Corp" 
                    />
                  </div>
                </div>

                {/* Work Email */}
                <div className="flex flex-col gap-2">
                  <label className="text-gray-900 text-sm font-medium leading-normal">Work Email</label>
                  <input 
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 bg-white h-12 px-4 text-gray-900 placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                    placeholder="name@company.com" 
                  />
                </div>

                {/* Password */}
                <div className="flex flex-col gap-2">
                  <label className="text-gray-900 text-sm font-medium leading-normal">Password</label>
                  <div className="relative flex w-full items-center">
                    <input 
                      type={showPassword ? "text" : "password"}
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full rounded-lg border border-gray-300 bg-white h-12 px-4 pr-12 text-gray-900 placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                      placeholder="••••••••" 
                    />
                    <button 
                      type="button" 
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-0 top-0 bottom-0 flex items-center justify-center px-4 cursor-pointer text-slate-400 hover:text-gray-900 transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                {/* Confirm Password */}
                <div className="flex flex-col gap-2">
                  <label className="text-gray-900 text-sm font-medium leading-normal">Confirm Password</label>
                  <div className="relative flex w-full items-center">
                    <input 
                      type={showPassword ? "text" : "password"}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full rounded-lg border border-gray-300 bg-white h-12 px-4 pr-12 text-gray-900 placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all duration-200 shadow-sm" 
                      placeholder="••••••••" 
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
                    <span>{isLoading ? 'Creating Account...' : 'Sign Up'}</span>
                    {!isLoading && <ArrowRight className="w-5 h-5" />}
                  </button>
                </div>

                {/* Footer Link */}
                <div className="text-center mt-2">
                  <p className="text-slate-500 text-sm">
                    Already have an account? 
                    <Link href="/login" className="text-primary hover:text-blue-600 font-medium transition-colors hover:underline ml-1">
                      Login
                    </Link>
                  </p>
                </div>
              </form>
            </div>

            <div className="mt-8 flex justify-center gap-6 text-xs text-slate-500 drop-shadow-sm">
              <Link href="/privacy" className="hover:text-primary transition-colors">Privacy Policy</Link>
              <Link href="/terms" className="hover:text-primary transition-colors">Terms of Service</Link>
              <Link href="/support" className="hover:text-primary transition-colors">Help Center</Link>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
