'use client';

import { useState, useEffect } from 'react';
import { Search, Upload, Download, Filter, MoreVertical, TrendingUp, Group, AlertTriangle } from 'lucide-react';
import { customersApi } from '@/lib/api';
import type { CustomerInsight } from '@/types';

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CustomerInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In a real implementation with pagination we'd use parameters
    customersApi.list({ page: 0, page_size: 50 }).then(res => {
      setCustomers(res.data);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8">
      <div className="mx-auto max-w-7xl flex flex-col gap-6 animate-fade-in">
        
        {/* Page Heading & Actions */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-gray-900 dark:text-white text-3xl font-black tracking-tight">Customer Profiles</h1>
            <p className="text-slate-500 dark:text-slate-400 text-base">Manage and analyze your customer base with AI-driven insights.</p>
          </div>
          <div className="flex gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-surface-elevated hover:bg-gray-50 dark:hover:bg-[#2a3c50] border border-gray-200 dark:border-surface-border rounded-lg text-gray-700 dark:text-white font-medium text-sm transition-colors cursor-pointer">
              <Upload className="w-5 h-5" />
              Import
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover rounded-lg text-white font-medium text-sm shadow-lg shadow-primary/20 transition-colors cursor-pointer">
              <Download className="w-5 h-5" />
              Export Data
            </button>
          </div>
        </div>

        {/* Filters & Controls Bar */}
        <div className="bg-white dark:bg-surface-elevated rounded-xl p-4 border border-gray-200 dark:border-surface-border shadow-sm">
          <div className="flex flex-col md:flex-row gap-4 justify-between items-center">
            {/* Table Search */}
            <div className="w-full md:w-auto flex-1 max-w-md relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
              <input 
                className="w-full h-10 pl-10 pr-4 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg text-gray-900 dark:text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none placeholder-slate-400" 
                placeholder="Search by name, ID, or email..." 
                type="text"
              />
            </div>
            
            {/* Filter & Sort */}
            <div className="flex gap-3 w-full md:w-auto">
              <div className="flex items-center gap-2 px-3 h-10 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg">
                <span className="text-slate-500 dark:text-slate-400 text-sm font-medium">Sort by:</span>
                <select className="bg-transparent border-none text-gray-900 dark:text-white text-sm font-medium focus:ring-0 p-0 pr-6 cursor-pointer outline-none">
                  <option>Highest LTV</option>
                  <option>Lowest LTV</option>
                  <option>Newest Customers</option>
                  <option>Most Orders</option>
                </select>
              </div>
              <button className="h-10 px-3 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg text-slate-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white flex items-center justify-center gap-2 transition-colors cursor-pointer">
                <Filter className="w-5 h-5" />
                <span className="text-sm font-medium hidden sm:block">Filters</span>
              </button>
            </div>
          </div>
        </div>

        {/* Data Table */}
        <div className="bg-white dark:bg-surface-elevated rounded-xl border border-gray-200 dark:border-surface-border overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[800px]">
              <thead>
                <tr className="border-b border-gray-200 dark:border-surface-border bg-gray-50 dark:bg-background-dark/50">
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap">
                    Customer ID
                  </th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap">Location</th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap">
                    First Purchase
                  </th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap text-right">Total Orders</th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-primary whitespace-nowrap text-right">
                    Lifetime Value (LTV)
                  </th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap">
                    AI Segment
                  </th>
                  <th className="p-4 w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-surface-border">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-500">Loading customers...</td>
                  </tr>
                ) : customers.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-500">No customers found. Import data to get started.</td>
                  </tr>
                ) : (
                  customers.map((c) => (
                    <tr key={c.id} className="group hover:bg-gray-50 dark:hover:bg-surface-border/40 transition-colors">
                      <td className="p-4">
                        <div className="flex flex-col">
                          <span className="text-gray-900 dark:text-white text-sm font-medium">{c.customer_id}</span>
                          <span className="text-slate-500 dark:text-slate-400 text-xs truncate max-w-[150px]">{c.customer_id.toLowerCase().replace(/[^a-z0-9]/g, '')}@example.com</span>
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2 text-gray-900 dark:text-white text-sm">
                          {c.location || 'Unknown'}
                        </div>
                      </td>
                      <td className="p-4 text-slate-500 dark:text-slate-400 text-sm">{c.first_purchase_date || 'N/A'}</td>
                      <td className="p-4 text-gray-900 dark:text-white text-sm font-medium text-right">{c.total_orders}</td>
                      <td className="p-4 text-right">
                        <span className="text-gray-900 dark:text-white font-bold text-sm bg-gray-100 dark:bg-surface-elevated px-2 py-1 rounded border border-gray-200 dark:border-surface-border">
                          ${c.lifetime_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                        </span>
                      </td>
                      <td className="p-4">
                        {c.predicted_segment === 'Champions' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 dark:bg-purple-500/10 text-purple-700 dark:text-purple-400 border border-purple-200 dark:border-purple-500/20">
                            VIP Champion
                          </span>
                        ) : c.predicted_segment === 'Loyal' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20">
                            Loyalist
                          </span>
                        ) : c.predicted_segment === 'At-Risk' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-500/20">
                            At-Risk
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">
                            {c.predicted_segment || 'New'}
                          </span>
                        )}
                      </td>
                      <td className="p-4 text-right">
                        <button className="text-slate-400 hover:text-gray-900 dark:hover:text-white p-1 rounded hover:bg-gray-200 dark:hover:bg-white/5 opacity-0 group-hover:opacity-100 transition-all cursor-pointer">
                          <MoreVertical className="w-5 h-5" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          
          {/* Pagination */}
          <div className="border-t border-gray-200 dark:border-surface-border bg-gray-50 dark:bg-background-dark p-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500 dark:text-slate-400">Rows per page:</span>
              <select className="bg-white dark:bg-surface-elevated border border-gray-200 dark:border-surface-border text-gray-900 dark:text-white text-sm rounded cursor-pointer outline-none py-1 pl-2 pr-8">
                <option>10</option>
                <option>20</option>
                <option>50</option>
              </select>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-slate-500 dark:text-slate-400">1-{Math.min(customers.length, 10)} of {Math.max(customers.length, 450)}</span>
              <div className="flex gap-1">
                <button className="p-1 rounded hover:bg-gray-200 dark:hover:bg-surface-elevated text-slate-400 hover:text-gray-900 dark:hover:text-white disabled:opacity-50 cursor-pointer" disabled>
                  {'<'}
                </button>
                <button className="p-1 rounded hover:bg-gray-200 dark:hover:bg-surface-elevated text-slate-400 hover:text-gray-900 dark:hover:text-white cursor-pointer">
                  {'>'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Footer / Additional Info */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pb-8">
          <div className="bg-white dark:bg-surface-elevated p-4 rounded-xl border border-gray-200 dark:border-surface-border flex items-start gap-3 shadow-sm">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <TrendingUp className="w-6 h-6" />
            </div>
            <div>
              <p className="text-slate-500 dark:text-slate-400 text-sm">Average LTV</p>
              <p className="text-gray-900 dark:text-white text-xl font-bold mt-1">$4,250</p>
              <p className="text-emerald-500 text-xs mt-1 flex items-center font-medium">
                +12% vs last month
              </p>
            </div>
          </div>
          <div className="bg-white dark:bg-surface-elevated p-4 rounded-xl border border-gray-200 dark:border-surface-border flex items-start gap-3 shadow-sm">
            <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-400">
              <Group className="w-6 h-6" />
            </div>
            <div>
              <p className="text-slate-500 dark:text-slate-400 text-sm">New VIPs</p>
              <p className="text-gray-900 dark:text-white text-xl font-bold mt-1">24</p>
              <p className="text-slate-500 dark:text-slate-400 text-xs mt-1">Identified this week</p>
            </div>
          </div>
          <div className="bg-white dark:bg-surface-elevated p-4 rounded-xl border border-gray-200 dark:border-surface-border flex items-start gap-3 shadow-sm">
            <div className="p-2 rounded-lg bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <p className="text-slate-500 dark:text-slate-400 text-sm">At-Risk Accounts</p>
              <p className="text-gray-900 dark:text-white text-xl font-bold mt-1">8</p>
              <p className="text-red-500 text-xs mt-1 font-medium">
                Needs attention
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
