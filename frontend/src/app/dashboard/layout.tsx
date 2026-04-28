'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, Package, Users, BarChart3, TrendingUp, PieChart, Settings, Bell, LogOut, User } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useState, useRef, useEffect } from 'react';

const NAV_LINKS = [
  { name: 'Home', href: '/dashboard', icon: Home },
  { name: 'Products', href: '/dashboard/products', icon: Package },
  { name: 'Customers', href: '/dashboard/customers', icon: Users },
  { name: 'Analytics', href: '/dashboard/analytics', icon: BarChart3 },
  { name: 'Forecasting', href: '/dashboard/forecasting', icon: TrendingUp },
  { name: 'Segmentation', href: '/dashboard/segmentation', icon: PieChart },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(event.target as Node)) {
        setIsNotificationsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background-light dark:bg-background-dark text-slate-900 dark:text-white font-sans">
      {/* Side Navigation */}
      <aside className="flex w-64 flex-col justify-between border-r border-gray-200 dark:border-surface-border bg-white dark:bg-background-dark p-4">
        <div className="flex flex-col gap-8">
          {/* Logo */}
          <div className="flex items-center gap-3 px-2 mt-2">
            <h1 className="text-gray-900 dark:text-white text-lg font-bold leading-normal tracking-tight">InsightX</h1>
          </div>
          
          {/* Menu Items */}
          <nav className="flex flex-col gap-2">
            {NAV_LINKS.map((link) => {
              const Icon = link.icon;
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.name}
                  href={link.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group ${
                    isActive 
                      ? 'bg-primary text-white shadow-sm' 
                      : 'text-slate-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-surface-card hover:text-gray-900 dark:hover:text-white'
                  }`}
                >
                  <Icon className={`w-5 h-5 ${isActive ? 'text-white' : 'group-hover:text-gray-900 dark:group-hover:text-white'}`} />
                  <p className="text-sm font-medium leading-normal">{link.name}</p>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Bottom Settings */}
        <div className="flex flex-col gap-2 border-t border-gray-200 dark:border-surface-border pt-4">
          <Link
            href="/dashboard/settings"
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group ${
              pathname === '/dashboard/settings'
                ? 'bg-primary text-white shadow-sm'
                : 'text-slate-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-surface-card hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <Settings className={`w-5 h-5 ${pathname === '/dashboard/settings' ? 'text-white' : 'group-hover:text-gray-900 dark:group-hover:text-white'}`} />
            <p className="text-sm font-medium leading-normal">Settings</p>
          </Link>
          <div className="flex flex-col space-y-1.5 px-3 py-2 mt-2 border-t border-gray-100 dark:border-surface-border/50">
            <Link href="/support" className="text-xs text-slate-400 hover:text-primary transition-colors">Support</Link>
            <Link href="/terms" className="text-xs text-slate-400 hover:text-primary transition-colors">Terms</Link>
            <Link href="/privacy" className="text-xs text-slate-400 hover:text-primary transition-colors">Privacy</Link>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex flex-1 flex-col h-full relative overflow-y-auto custom-scrollbar">
        {/* Header */}
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-gray-200 dark:border-surface-border bg-white/95 dark:bg-background-dark/95 backdrop-blur px-8 py-4">
          <div className="flex items-center gap-4">
            <h2 className="text-gray-900 dark:text-white text-xl font-bold">Dashboard</h2>
          </div>
          
          <div className="flex items-center gap-6">
            <Link href="/dashboard/upload" className="btn btn-primary btn-sm flex items-center gap-2">
              <span className="text-lg leading-none">+</span> New Analysis
            </Link>
            
            {/* Notification Bell */}
            <div className="relative" ref={notificationsRef}>
              <button 
                onClick={() => setIsNotificationsOpen(!isNotificationsOpen)}
                className="relative flex items-center justify-center w-10 h-10 rounded-full hover:bg-gray-100 dark:hover:bg-surface-card text-slate-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white transition-colors"
              >
                <Bell className="w-5 h-5" />
                <span className="absolute top-2.5 right-2.5 w-2 h-2 bg-red-500 rounded-full border border-white dark:border-background-dark"></span>
              </button>
              
              {isNotificationsOpen && (
                <div className="absolute right-0 mt-2 w-80 bg-white dark:bg-surface-card border border-gray-200 dark:border-surface-border rounded-xl shadow-lg z-50 overflow-hidden">
                  <div className="p-4 border-b border-gray-100 dark:border-surface-border">
                    <h3 className="font-semibold text-gray-900 dark:text-white">Notifications</h3>
                  </div>
                  <div className="py-2 flex flex-col max-h-96 overflow-y-auto custom-scrollbar">
                    <div className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-background-dark/50 cursor-pointer border-l-4 border-primary transition-colors">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">Analysis Complete</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Your recent CSV upload has been processed successfully.</p>
                      <p className="text-xs text-slate-400 dark:text-slate-500 mt-2 text-right">Just now</p>
                    </div>
                    <div className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-background-dark/50 cursor-pointer border-l-4 border-transparent transition-colors">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">Welcome to InsightX</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Your account has been set up successfully. Explore your dashboard to get started.</p>
                      <p className="text-xs text-slate-400 dark:text-slate-500 mt-2 text-right">2 hours ago</p>
                    </div>
                  </div>
                  <div className="p-3 border-t border-gray-100 dark:border-surface-border text-center bg-gray-50 dark:bg-surface-card/50">
                    <button className="text-sm text-primary hover:text-primary/80 font-medium transition-colors">View All Notifications</button>
                  </div>
                </div>
              )}
            </div>
            
            {/* User Profile */}
            <div className="relative" ref={profileRef}>
              <button 
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="flex items-center gap-3 cursor-pointer outline-none"
              >
                <div className="rounded-full h-10 w-10 border-2 border-gray-200 dark:border-surface-border bg-primary/20 flex items-center justify-center text-primary font-bold hover:border-primary/50 transition-colors">
                  {user?.full_name?.[0]?.toUpperCase() || 'U'}
                </div>
              </button>
              
              {isProfileOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-surface-card border border-gray-200 dark:border-surface-border rounded-xl shadow-lg z-50 overflow-hidden">
                  <div className="p-4 border-b border-gray-100 dark:border-surface-border">
                    <p className="font-medium text-gray-900 dark:text-white truncate">{user?.full_name || 'User'}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">{user?.email || 'user@example.com'}</p>
                  </div>
                  <div className="py-1">
                    <Link 
                      href="/dashboard/settings" 
                      onClick={() => setIsProfileOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-background-dark/50 hover:text-gray-900 dark:hover:text-white transition-colors"
                    >
                      <User className="w-4 h-4" />
                      <span>Profile Settings</span>
                    </Link>
                  </div>
                  <div className="py-1 border-t border-gray-100 dark:border-surface-border">
                    <button 
                      onClick={() => {
                        setIsProfileOpen(false);
                        logout();
                      }}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Sign out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Dynamic Route Content */}
        {children}
      </main>
    </div>
  );
}
