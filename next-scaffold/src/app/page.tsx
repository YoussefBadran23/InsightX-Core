'use client';

import Link from 'next/link';

export default function LandingPage() {
  return (
    <div className="bg-background-light dark:bg-background-dark text-slate-800 dark:text-text-primary font-sans transition-colors duration-300 min-h-screen flex flex-col">
      <header className="fixed w-full top-0 z-50 glass border-b border-gray-200 dark:border-surface-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <div className="flex items-center space-x-3">
              <span className="font-bold text-2xl tracking-tight text-gray-900 dark:text-white">
                Insight<span className="text-primary">X</span>
              </span>
            </div>
            <div className="flex items-center space-x-4">
              <Link href="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white transition-colors">
                Login
              </Link>
              <Link href="/signup" className="bg-primary hover:bg-primary-hover text-white text-sm font-medium py-2 px-5 rounded-full transition-all shadow-lg shadow-primary/30">
                Sign Up
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-grow flex items-center relative overflow-hidden pt-20">
        <div className="absolute inset-0 z-0">
          <div className="absolute inset-0 bg-white/90 dark:bg-background-dark/80 z-10"></div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img alt="Abstract connectivity network background" className="w-full h-full object-cover" src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop"/>
        </div>
        
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-20 z-0 animate-pulse-slow"></div>
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-96 h-96 bg-primary rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-20 z-0 animate-pulse-slow font-delay-2000"></div>
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-20 w-full py-12 lg:py-24">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
            
            {/* Left Column: Copy */}
            <div className="lg:col-span-6 flex flex-col justify-center text-center lg:text-left space-y-8">
              <div className="space-y-4">
                <h1 className="font-bold text-5xl lg:text-7xl leading-tight text-gray-900 dark:text-white">
                  Stop Guessing. <br/>
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-purple-500 to-pink-500">Start Forecasting.</span>
                </h1>
                <p className="text-lg text-slate-600 dark:text-slate-400 max-w-lg mx-auto lg:mx-0 font-light leading-relaxed">
                  Transform raw data into actionable foresight. InsightX empowers your business with AI-driven analytics that see beyond the numbers.
                </p>
              </div>
              <div className="flex flex-col sm:flex-row items-center gap-4 justify-center lg:justify-start">
                <Link href="/signup" className="w-full sm:w-auto bg-primary hover:bg-primary-hover text-white font-semibold py-4 px-8 rounded-lg shadow-xl shadow-primary/20 transition-all transform hover:-translate-y-0.5 flex items-center justify-center space-x-2">
                  <span>Start Analysis Free</span>
                  <span>→</span>
                </Link>
                <Link href="/login" className="w-full sm:w-auto bg-transparent border border-gray-300 dark:border-surface-border hover:bg-gray-100 dark:hover:bg-surface-elevated text-gray-900 dark:text-white font-medium py-4 px-8 rounded-lg transition-all flex items-center justify-center space-x-2">
                  <span>View Dashboard</span>
                </Link>
              </div>
              <div className="pt-8 flex items-center justify-center lg:justify-start space-x-6 text-sm text-slate-500 dark:text-slate-400">
                <div className="flex items-center space-x-2">
                  <span className="text-emerald-500 text-base">✓</span>
                  <span>No credit card required</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-emerald-500 text-base">✓</span>
                  <span>14-day free trial</span>
                </div>
              </div>
            </div>
            
            {/* Right Column: Grid */}
            <div className="lg:col-span-6 relative">
              <div className="absolute inset-0 bg-gradient-to-tr from-primary/20 to-purple-500/20 rounded-full filter blur-3xl opacity-30"></div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 relative">
                
                <div className="glass-card p-6 border dark:border-white/5 hover:bg-white/50 dark:hover:border-primary/30 transition-all cursor-pointer group">
                  <div className="h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center mb-4 text-blue-600 dark:text-blue-400 transition-transform">
                    <span className="text-2xl">☁️</span>
                  </div>
                  <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1">Start</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Upload Data effortlessly via CSV or API.</p>
                </div>
                
                <div className="glass-card p-6 border dark:border-white/5 hover:bg-white/50 dark:hover:border-primary/30 transition-all cursor-pointer group mt-0 sm:mt-8">
                  <div className="h-12 w-12 rounded-lg bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center mb-4 text-indigo-600 dark:text-indigo-400 transition-transform">
                    <span className="text-2xl">📊</span>
                  </div>
                  <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1">Analytics</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Deep Dive into real-time metrics.</p>
                </div>
                
                <div className="glass-card p-6 border dark:border-white/5 hover:bg-white/50 dark:hover:border-primary/30 transition-all cursor-pointer group">
                  <div className="h-12 w-12 rounded-lg bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center mb-4 text-purple-600 dark:text-purple-400 transition-transform">
                    <span className="text-2xl">🔮</span>
                  </div>
                  <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1">Forecasting</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">AI Predictions for future trends.</p>
                </div>
                
                <div className="glass-card p-6 border dark:border-white/5 hover:bg-white/50 dark:hover:border-primary/30 transition-all cursor-pointer group mt-0 sm:mt-8">
                  <div className="h-12 w-12 rounded-lg bg-pink-100 dark:bg-pink-900/50 flex items-center justify-center mb-4 text-pink-600 dark:text-pink-400 transition-transform">
                    <span className="text-2xl">🎯</span>
                  </div>
                  <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1">Segmentation</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Customer Clusters & behavior analysis.</p>
                </div>
                
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="glass border-t border-gray-200 dark:border-surface-border relative z-30">
        <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
            <div className="flex space-x-8">
              <Link className="text-sm text-slate-500 hover:text-primary transition-colors" href="/support">Support</Link>
              <Link className="text-sm text-slate-500 hover:text-primary transition-colors" href="/terms">Terms</Link>
              <Link className="text-sm text-slate-500 hover:text-primary transition-colors" href="/privacy">Privacy</Link>
            </div>
          </div>
          <div className="mt-4 text-center text-xs text-gray-400 dark:text-gray-500">
            © 2026 InsightX. See Beyond.
          </div>
        </div>
      </footer>
    </div>
  );
}
