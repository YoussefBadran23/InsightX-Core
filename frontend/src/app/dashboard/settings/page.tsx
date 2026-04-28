'use client';

import { useAuthStore } from '@/stores/authStore';
import { LogOut, User, Settings as SettingsIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function SettingsPage() {
  const { user, logout } = useAuthStore();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 animate-fade-in">
      <div className="mx-auto max-w-4xl flex flex-col gap-6">
        
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">Settings</h1>
          <p className="text-slate-500 dark:text-slate-400">Manage your account and preferences.</p>
        </div>

        <div className="bg-white dark:bg-surface-elevated rounded-xl shadow-sm border border-gray-200 dark:border-surface-border overflow-hidden">
          <div className="p-6 border-b border-gray-200 dark:border-surface-border flex items-center gap-4">
            <div className="w-16 h-16 bg-primary/10 text-primary rounded-full flex items-center justify-center font-bold text-2xl border-2 border-primary/20">
              {user?.full_name?.[0]?.toUpperCase() || 'U'}
            </div>
            <div>
               <h2 className="text-xl font-bold text-gray-900 dark:text-white">{user?.full_name || 'System User'}</h2>
               <p className="text-sm text-slate-500 dark:text-slate-400">{user?.email || 'admin@insightx.com'}</p>
            </div>
          </div>

          <div className="p-6">
            <h3 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider mb-4 flex items-center gap-2">
              <SettingsIcon className="w-4 h-4" /> Account Actions
            </h3>
            
            <button 
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-500/20 hover:bg-red-100 dark:hover:bg-red-500/20 rounded-lg transition-colors font-medium"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
