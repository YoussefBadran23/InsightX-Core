'use client';

import { useEffect, useState } from 'react';
import { DollarSign, Users, TrendingDown, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { kpiApi } from '@/lib/api';
import type { KpiSummary } from '@/types';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useRouter } from 'next/navigation';

export default function DashboardHome() {
  const [data, setData] = useState<KpiSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    kpiApi.summary().then((res) => {
      // If the user has absolutely no data, redirect to the upload page automatically
      if (res.data && res.data.total_revenue === 0 && res.data.active_customers === 0) {
        router.push('/dashboard/upload');
        return;
      }
      setData(res.data);
      setLoading(false);
    }).catch(() => {
      // Handle error cleanly
      setLoading(false);
    });
  }, [router]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  // Mock chart data to fit the UI until we plug in the history API
  const chartData = [
    { name: 'Day 1', value: 120 },
    { name: 'Day 5', value: 130 },
    { name: 'Day 10', value: 110 },
    { name: 'Day 15', value: 160 },
    { name: 'Day 20', value: 140 },
    { name: 'Day 25', value: 180 },
    { name: 'Day 30', value: 210 },
  ];

  return (
    <div className="flex-1 p-8">
      <div className="mx-auto max-w-7xl flex flex-col gap-6 animate-fade-in">
        
        {/* KPI Cards Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Revenue */}
          <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 shadow-sm">
            <div className="flex justify-between items-start">
              <p className="text-slate-500 dark:text-slate-400 text-sm font-medium leading-normal">Total Revenue</p>
              <DollarSign className="text-primary w-6 h-6" />
            </div>
            <div className="flex items-baseline gap-3 mt-1">
              <p className="text-gray-900 dark:text-white tracking-tight text-3xl font-bold leading-tight">
                ${data ? (data.total_revenue / 1000).toFixed(1) + 'k' : '0.0k'}
              </p>
              {data?.revenue_delta && data.revenue_delta.change_pct !== null && (
                <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-sm font-medium ${
                  data.revenue_delta.direction === 'up' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-500' : 'bg-red-500/10 text-red-600 dark:text-red-500'
                }`}>
                  {data.revenue_delta.direction === 'up' ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                  <span>{Math.abs(data.revenue_delta.change_pct)}%</span>
                </div>
              )}
            </div>
          </div>

          {/* Customers */}
          <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 shadow-sm">
            <div className="flex justify-between items-start">
              <p className="text-slate-500 dark:text-slate-400 text-sm font-medium leading-normal">Active Customers</p>
              <Users className="text-primary w-6 h-6" />
            </div>
            <div className="flex items-baseline gap-3 mt-1">
              <p className="text-gray-900 dark:text-white tracking-tight text-3xl font-bold leading-tight">
                {data?.active_customers || 0}
              </p>
              {data?.customers_delta && data.customers_delta.change_pct !== null && (
                <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-sm font-medium ${
                  data.customers_delta.direction === 'up' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-500' : 'bg-red-500/10 text-red-600 dark:text-red-500'
                }`}>
                  {data.customers_delta.direction === 'up' ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                  <span>{Math.abs(data.customers_delta.change_pct)}%</span>
                </div>
              )}
            </div>
          </div>

          {/* Churn */}
          <div className="flex flex-col gap-2 rounded-xl p-6 bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 shadow-sm">
            <div className="flex justify-between items-start">
              <p className="text-slate-500 dark:text-slate-400 text-sm font-medium leading-normal">Churn Rate</p>
              <TrendingDown className="text-primary w-6 h-6" />
            </div>
            <div className="flex items-baseline gap-3 mt-1">
              <p className="text-gray-900 dark:text-white tracking-tight text-3xl font-bold leading-tight">
                {data ? `${data.churn_rate}%` : '0%'}
              </p>
            </div>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-slide-up">
          
          {/* Main Visual: Sales Trend */}
          <div className="lg:col-span-2 rounded-xl bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 p-6 shadow-sm">
            <div className="flex flex-col gap-1 mb-6">
              <h3 className="text-gray-900 dark:text-white text-lg font-bold leading-normal">Sales Trend Last 30 Days</h3>
              <div className="flex gap-2 items-center">
                <p className="text-slate-500 text-sm">Compared to previous month</p>
                {data?.revenue_delta?.direction === 'up' && (
                  <span className="text-emerald-500 text-sm font-medium">+{data.revenue_delta.change_pct}%</span>
                )}
              </div>
            </div>
            
            {/* Recharts Area Chart */}
            <div className="w-full h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#137fec" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#137fec" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} opacity={0.6} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 12 }} opacity={0.6} tickLine={false} axisLine={false} tickFormatter={(val) => `$${val}k`} />
                  <Tooltip wrapperClassName="dark:!bg-surface !bg-white !rounded-lg !border-surface-border" />
                  <Area type="monotone" dataKey="value" stroke="#137fec" strokeWidth={3} fillOpacity={1} fill="url(#colorValue)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Sub-Visual: Revenue by Region */}
          <div className="rounded-xl bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 p-6 shadow-sm flex flex-col">
            <div className="flex flex-col gap-1 mb-6">
              <h3 className="text-gray-900 dark:text-white text-lg font-bold leading-normal">Revenue by Region</h3>
            </div>
            
            <div className="flex-1 flex items-end justify-between px-2 gap-4">
              {[
                { name: 'NA', val: data?.revenue_na || 0, max: 100 },
                { name: 'EU', val: data?.revenue_eu || 0, max: 100 },
                { name: 'APAC', val: data?.revenue_apac || 0, max: 100 },
                { name: 'LATAM', val: data?.revenue_latam || 0, max: 100 },
              ].map((r) => {
                // simple calc for height %
                let h = 10;
                if (data && data.total_revenue > 0) {
                  h = Math.max(10, Math.min(100, (Number(r.val) / Number(data.total_revenue)) * 100 * 1.5));
                }
                
                return (
                  <div key={r.name} className="flex flex-col items-center gap-2 w-full">
                    <div className="w-full rounded-t-sm bg-gray-100 dark:bg-slate-700/30 relative h-48 flex items-end overflow-hidden group">
                      <div 
                        className="w-full bg-primary group-hover:bg-primary-hover transition-all duration-500 rounded-t-sm" 
                        style={{ height: `${h}%` }}
                      ></div>
                    </div>
                    <p className="text-slate-500 text-xs font-bold">{r.name}</p>
                  </div>
                );
              })}
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}
