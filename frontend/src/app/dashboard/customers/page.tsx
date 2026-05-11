'use client';

import { useState, useEffect, useMemo } from 'react';
import { Search, Upload, Download, Filter, MoreVertical, TrendingUp, Group, AlertTriangle } from 'lucide-react';
import { customersApi } from '@/lib/api';
import { useUiStore } from '@/stores/uiStore';
import { t, tp } from '@/lib/i18n';
import type { Customer } from '@/types';
import { SEGMENT_CONFIG } from '@/types';

const PAGE_SIZE = 25;

export default function CustomersPage() {
  const language = useUiStore((s) => s.language);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('lifetime_value');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    setLoading(true);
    customersApi
      .list({ page, page_size: PAGE_SIZE, search: search || undefined, sort_by: sortBy, sort_dir: sortDir })
      .then((res) => {
        const env = res.data as { total: number; pages: number; items: Customer[] };
        setCustomers(env.items || []);
        setTotal(env.total ?? 0);
        setPages(env.pages ?? 1);
      })
      .catch(() => {
        setCustomers([]);
        setTotal(0);
        setPages(1);
      })
      .finally(() => setLoading(false));
  }, [page, search, sortBy, sortDir]);

  // ── Real summary metrics derived from current page (P0: not perfect, but live) ──
  const summary = useMemo(() => {
    if (customers.length === 0) {
      return { avgLtv: 0, vipCount: 0, atRiskCount: 0 };
    }
    const avgLtv = customers.reduce((sum, c) => sum + (Number(c.lifetime_value) || 0), 0) / customers.length;
    const vipCount = customers.filter((c) => c.ai_segment === 'vip_champion').length;
    const atRiskCount = customers.filter((c) => c.ai_segment === 'at_risk').length;
    return { avgLtv, vipCount, atRiskCount };
  }, [customers]);

  const segmentBadge = (seg: Customer['ai_segment']) => {
    const cfg = seg ? SEGMENT_CONFIG[seg] : null;
    if (!cfg) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-500/20">
          —
        </span>
      );
    }
    // Color-coded badges by segment family
    const colorClass =
      seg === 'vip_champion'
        ? 'bg-purple-100 dark:bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-200 dark:border-purple-500/20'
        : seg === 'loyalist'
        ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20'
        : seg === 'at_risk'
        ? 'bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20'
        : 'bg-emerald-100 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20';
    return (
      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${colorClass}`}>
        {cfg.icon} {cfg.label}
      </span>
    );
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8">
      <div className="mx-auto max-w-7xl flex flex-col gap-6 animate-fade-in">
        {/* Page heading */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-gray-900 dark:text-white text-3xl font-black tracking-tight">{t('cust_title', language)}</h1>
            <p className="text-slate-500 dark:text-slate-400 text-base">
              {loading ? t('cust_loading', language) : `${total.toLocaleString()} ${t('cust_count', language)}`}
            </p>
          </div>
          <div className="flex gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-surface-elevated hover:bg-gray-50 dark:hover:bg-[#2a3c50] border border-gray-200 dark:border-surface-border rounded-lg text-gray-700 dark:text-white font-medium text-sm transition-colors cursor-pointer">
              <Upload className="w-5 h-5" />
              {t('cust_import', language)}
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover rounded-lg text-white font-medium text-sm shadow-lg shadow-primary/20 transition-colors cursor-pointer">
              <Download className="w-5 h-5" />
              {t('cust_export', language)}
            </button>
          </div>
        </div>

        {/* Filters bar */}
        <div className="bg-white dark:bg-surface-elevated rounded-xl p-4 border border-gray-200 dark:border-surface-border shadow-sm">
          <div className="flex flex-col md:flex-row gap-4 justify-between items-center">
            <div className="w-full md:w-auto flex-1 max-w-md relative">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
              <input
                className="w-full h-10 ps-10 pe-4 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg text-gray-900 dark:text-white text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none placeholder-slate-400"
                placeholder={t('cust_searchPlaceholder', language)}
                type="text"
                value={search}
                onChange={(e) => {
                  setPage(1);
                  setSearch(e.target.value);
                }}
              />
            </div>

            <div className="flex gap-3 w-full md:w-auto">
              <div className="flex items-center gap-2 px-3 h-10 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg">
                <span className="text-slate-500 dark:text-slate-400 text-sm font-medium">{t('cust_sortBy', language)}</span>
                <select
                  className="bg-transparent border-none text-gray-900 dark:text-white text-sm font-medium focus:ring-0 p-0 pe-6 cursor-pointer outline-none"
                  value={`${sortBy}|${sortDir}`}
                  onChange={(e) => {
                    const [by, dir] = e.target.value.split('|');
                    setSortBy(by);
                    setSortDir(dir as 'asc' | 'desc');
                    setPage(1);
                  }}
                >
                  <option value="lifetime_value|desc">{t('cust_sortHighestLtv', language)}</option>
                  <option value="lifetime_value|asc">{t('cust_sortLowestLtv', language)}</option>
                  <option value="first_purchase_date|desc">{t('cust_sortNewest', language)}</option>
                  <option value="total_orders|desc">{t('cust_sortMostOrders', language)}</option>
                </select>
              </div>
              <button className="h-10 px-3 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-lg text-slate-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white flex items-center justify-center gap-2 transition-colors cursor-pointer">
                <Filter className="w-5 h-5" />
                <span className="text-sm font-medium hidden sm:block">{t('cust_filters', language)}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Data table */}
        <div className="bg-white dark:bg-surface-elevated rounded-xl border border-gray-200 dark:border-surface-border overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-start border-collapse min-w-[800px]">
              <thead>
                <tr className="border-b border-gray-200 dark:border-surface-border bg-gray-50 dark:bg-background-dark/50">
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap text-start">{t('cust_thCustomer', language)}</th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap text-start">{t('cust_thLocation', language)}</th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap text-start">{t('cust_thFirstPurchase', language)}</th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap text-end">{t('cust_thOrders', language)}</th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-primary whitespace-nowrap text-end">{t('cust_thLtv', language)}</th>
                  <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 whitespace-nowrap text-start">{t('cust_thSegment', language)}</th>
                  <th className="p-4 w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-surface-border">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-500">
                      {t('cust_loadingRow', language)}
                    </td>
                  </tr>
                ) : customers.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-500">
                      {t('cust_emptyRow', language)}
                    </td>
                  </tr>
                ) : (
                  customers.map((c) => (
                    <tr key={c.id} className="group hover:bg-gray-50 dark:hover:bg-surface-border/40 transition-colors">
                      <td className="p-4">
                        <div className="flex flex-col">
                          <span className="text-gray-900 dark:text-white text-sm font-medium">
                            {c.full_name || c.external_id || c.email}
                          </span>
                          <span className="text-slate-500 dark:text-slate-400 text-xs truncate max-w-[220px]">
                            {c.email}
                          </span>
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2 text-gray-900 dark:text-white text-sm">
                          {[c.region, c.country].filter(Boolean).join(', ') || t('cust_unknownLocation', language)}
                        </div>
                      </td>
                      <td className="p-4 text-slate-500 dark:text-slate-400 text-sm">{c.first_purchase_date || 'N/A'}</td>
                      <td className="p-4 text-gray-900 dark:text-white text-sm font-medium text-end">{c.total_orders}</td>
                      <td className="p-4 text-end">
                        <span className="text-gray-900 dark:text-white font-bold text-sm bg-gray-100 dark:bg-surface-elevated px-2 py-1 rounded border border-gray-200 dark:border-surface-border">
                          ${Number(c.lifetime_value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </span>
                      </td>
                      <td className="p-4">{segmentBadge(c.ai_segment)}</td>
                      <td className="p-4 text-end">
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

          {/* Pagination — now functional */}
          <div className="border-t border-gray-200 dark:border-surface-border bg-gray-50 dark:bg-background-dark p-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t('cust_rowsPerPage', language)}: {PAGE_SIZE}</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-slate-500 dark:text-slate-400">
                {customers.length === 0
                  ? `0 of ${total}`
                  : `${(page - 1) * PAGE_SIZE + 1}–${(page - 1) * PAGE_SIZE + customers.length} of ${total.toLocaleString()}`}
              </span>
              <div className="flex gap-1">
                <button
                  className="p-1 rounded hover:bg-gray-200 dark:hover:bg-surface-elevated text-slate-400 hover:text-gray-900 dark:hover:text-white disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  {'<'}
                </button>
                <button
                  className="p-1 rounded hover:bg-gray-200 dark:hover:bg-surface-elevated text-slate-400 hover:text-gray-900 dark:hover:text-white disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                  disabled={page >= pages}
                  onClick={() => setPage((p) => Math.min(pages, p + 1))}
                >
                  {'>'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Real summary cards — computed from current page */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pb-8">
          <div className="bg-white dark:bg-surface-elevated p-4 rounded-xl border border-gray-200 dark:border-surface-border flex items-start gap-3 shadow-sm">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <TrendingUp className="w-6 h-6" />
            </div>
            <div>
              <p className="text-slate-500 dark:text-slate-400 text-sm">{t('cust_summaryAvgLtv', language)}</p>
              <p className="text-gray-900 dark:text-white text-xl font-bold mt-1">
                ${summary.avgLtv.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
              <p className="text-slate-500 text-xs mt-1">{tp('cust_summaryAvgLtvSub', language, { n: customers.length })}</p>
            </div>
          </div>
          <div className="bg-white dark:bg-surface-elevated p-4 rounded-xl border border-gray-200 dark:border-surface-border flex items-start gap-3 shadow-sm">
            <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-400">
              <Group className="w-6 h-6" />
            </div>
            <div>
              <p className="text-slate-500 dark:text-slate-400 text-sm">{t('cust_summaryVip', language)}</p>
              <p className="text-gray-900 dark:text-white text-xl font-bold mt-1">{summary.vipCount}</p>
              <p className="text-slate-500 dark:text-slate-400 text-xs mt-1">{t('cust_summaryVipSub', language)}</p>
            </div>
          </div>
          <div className="bg-white dark:bg-surface-elevated p-4 rounded-xl border border-gray-200 dark:border-surface-border flex items-start gap-3 shadow-sm">
            <div className="p-2 rounded-lg bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <p className="text-slate-500 dark:text-slate-400 text-sm">{t('cust_summaryAtRisk', language)}</p>
              <p className="text-gray-900 dark:text-white text-xl font-bold mt-1">{summary.atRiskCount}</p>
              <p className="text-red-500 text-xs mt-1 font-medium">{t('cust_summaryAtRiskSub', language)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
