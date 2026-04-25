'use client';

import { useJobStore } from '@/stores/jobStore';
import { Loader2, Database, LayoutDashboard } from 'lucide-react';
import Link from 'next/link';

export default function AnalyticsPage() {
  const { currentJobId, status, progress, modulesCompleted } = useJobStore();

  if (status === 'processing' || status === 'pending') {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 animate-fade-in">
        <div className="max-w-md w-full bg-white dark:bg-surface-elevated rounded-2xl shadow-xl border border-gray-200 dark:border-surface-border p-8 text-center relative overflow-hidden">
          {/* Progress Bar Top */}
          <div className="absolute top-0 left-0 w-full h-2 bg-gray-100 dark:bg-surface-border">
            <div 
              className="h-full bg-primary transition-all duration-500 ease-out" 
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          
          <div className="mb-8 mt-4 flex justify-center">
            <div className="relative">
              <div className="w-24 h-24 rounded-full border-4 border-gray-100 dark:border-surface-border flex items-center justify-center shadow-inner">
                <Loader2 className="w-10 h-10 text-primary animate-spin" />
              </div>
              <div className="absolute inset-0 rounded-full border-4 border-primary border-t-transparent animate-spin" style={{ animationDirection: 'reverse', animationDuration: '3s' }}></div>
            </div>
          </div>
          
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Analyzing Data Structure</h2>
          <p className="text-slate-500 dark:text-slate-400 mb-8">Our AI pipeline is currently crunching your numbers. This usually takes less than a minute.</p>
          
          <div className="space-y-4 text-left">
            <div className="flex items-center gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${modulesCompleted.includes('cleaning') ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400' : 'bg-gray-100 dark:bg-surface-border text-slate-400'}`}>✓</div>
              <span className={`text-sm ${modulesCompleted.includes('cleaning') ? 'text-gray-900 dark:text-white font-medium' : 'text-slate-400'}`}>Data Cleaning & Normalization</span>
            </div>
            <div className="flex items-center gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${modulesCompleted.includes('segmentation') ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400' : 'bg-gray-100 dark:bg-surface-border text-slate-400'}`}>✓</div>
              <span className={`text-sm ${modulesCompleted.includes('segmentation') ? 'text-gray-900 dark:text-white font-medium' : 'text-slate-400'}`}>Clustering & Segmentation Models</span>
            </div>
            <div className="flex items-center gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${modulesCompleted.includes('forecasting') ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400' : 'bg-gray-100 dark:bg-surface-border text-slate-400'}`}>✓</div>
              <span className={`text-sm ${modulesCompleted.includes('forecasting') ? 'text-gray-900 dark:text-white font-medium' : 'text-slate-400'}`}>Predictive Forecasting</span>
            </div>
          </div>
          
          <p className="mt-8 text-xs font-mono text-slate-400">Job ID: {currentJobId}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-8 animate-fade-in">
      <div className="mx-auto max-w-5xl flex flex-col items-center justify-center text-center mt-20">
        <div className="w-20 h-20 bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-500 rounded-full flex items-center justify-center mb-6">
          <Database className="w-10 h-10" />
        </div>
        <h1 className="text-4xl font-black text-gray-900 dark:text-white tracking-tight mb-4">Pipeline Complete</h1>
        <p className="text-lg text-slate-500 dark:text-slate-400 mb-8 max-w-2xl">
          Your data has been successfully ingested, cleaned, and analyzed by the ML pipeline. Your dashboard has been fully populated with the new insights.
        </p>
        <div className="flex gap-4">
          <Link href="/dashboard" className="px-6 py-3 bg-primary hover:bg-primary-hover text-white font-medium rounded-lg shadow-lg shadow-primary/20 transition-all flex items-center gap-2">
            <LayoutDashboard className="w-5 h-5" />
            Go to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
