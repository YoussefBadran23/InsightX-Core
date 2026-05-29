'use client';

import { useState, useEffect } from 'react';
import { Search, Download, MoreVertical, TrendingUp, Group, AlertTriangle, Loader2 } from 'lucide-react';
import { customersApi } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { useJobStore } from '@/stores/jobStore';
import { t } from '@/lib/i18n';
import { formatMoney } from '@/lib/format';
import type { Customer } from '@/types';
import { SEGMENT_CONFIG } from '@/types';

const PAGE_SIZE = 25;

export default function CustomersPage() {
  const language = useUiStore((s) => s.language);
  const currency = useAuthStore((s) => s.user?.preferred_currency) || 'USD';
  // Source currency from the latest upload — hydrated by DashboardLayout once
  // on mount via /kpi/summary, so by the time this page renders we already
  // know what currency the CSV's numbers are in.
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('lifetime_value');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [exporting, setExporting] = useState(false);
  // Aggregates over the WHOLE filtered set — backend already honors search /
  // segment / region filters when computing these, so we just mirror them
  // straight into the cards. Avg LTV is in source currency (USD for stock
  // seeds) and formatMoney converts to the user's display currency.
  const [summary, setSummary] = useState<{ avgLtv: number; vipCount: number; atRiskCount: number }>(
    { avgLtv: 0, vipCount: 0, atRiskCount: 0 },
  );

  // ── CSV export ───────────────────────────────────────────────────────────
  // Backend caps page_size at 100, so we page through everything that matches
  // the current search + sort. Identical pattern to the products page; kept
  // local here so the two stay independently maintainable.
  const escapeCsv = (val: unknown): string => {
    if (val === null || val === undefined) return '';
    const s = String(val);
    return `"${s.replace(/"/g, '""')}"`;
  };

  const handleExport = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const PAGE = 100;
      const MAX_PAGES = 1000; // 100k customers upper bound

      const firstRes = await customersApi.list({
        page: 1,
        page_size: PAGE,
        search: search || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      const firstEnv = firstRes.data as { pages: number; items: Customer[] };
      const all: Customer[] = [...(firstEnv.items || [])];
      const totalPages = Math.min(firstEnv.pages ?? 1, MAX_PAGES);

      for (let p = 2; p <= totalPages; p++) {
        const r = await customersApi.list({
          page: p,
          page_size: PAGE,
          search: search || undefined,
          sort_by: sortBy,
          sort_dir: sortDir,
        });
        const env = r.data as { items: Customer[] };
        if (!env?.items?.length) break;
        all.push(...env.items);
      }

      const header = [
        'external_id', 'email', 'full_name', 'country', 'region',
        'first_purchase_date', 'total_orders', 'lifetime_value', 'ai_segment',
        'rfm_segment', 'rfm_score', 'churn_risk_score', 'clv_predicted',
        'last_active_at', 'is_active',
      ];
      const rows = all.map((c) => [
        c.external_id ?? '', c.email, c.full_name ?? '', c.country ?? '',
        c.region ?? '', c.first_purchase_date ?? '', c.total_orders,
        c.lifetime_value, c.ai_segment ?? '', c.rfm_segment ?? '',
        c.rfm_score ?? '', c.churn_risk_score ?? '', c.clv_predicted ?? '',
        c.last_active_at ?? '', c.is_active,
      ]);

      const csv = [header, ...rows]
        .map((row) => row.map(escapeCsv).join(','))
        .join('\r\n');

      // BOM so Excel reads UTF-8 (Arabic names) correctly.
      const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const stamp = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `insightx_customers_${stamp}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('[customers export]', e);
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    customersApi
      .list({ page, page_size: PAGE_SIZE, search: search || undefined, sort_by: sortBy, sort_dir: sortDir })
      .then((res) => {
        const env = res.data as {
          total: number;
          pages: number;
          items: Customer[];
          summary?: {
            avg_lifetime_value: number | string;
            vip_count: number;
            at_risk_count: number;
          };
        };
        setCustomers(env.items || []);
        setTotal(env.total ?? 0);
        setPages(env.pages ?? 1);
        if (env.summary) {
          setSummary({
            avgLtv: Number(env.summary.avg_lifetime_value) || 0,
            vipCount: Number(env.summary.vip_count) || 0,
            atRiskCount: Number(env.summary.at_risk_count) || 0,
          });
        } else {
          setSummary({ avgLtv: 0, vipCount: 0, atRiskCount: 0 });
        }
      })
      .catch(() => {
        setCustomers([]);
        setTotal(0);
        setPages(1);
        setSummary({ avgLtv: 0, vipCount: 0, atRiskCount: 0 });
      })
      .finally(() => setLoading(false));
  }, [page, search, sortBy, sortDir]);

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
            <button
              onClick={handleExport}
              disabled={exporting || customers.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover rounded-lg text-white font-medium text-sm shadow-lg shadow-primary/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
            >
              {exporting
                ? <Loader2 className="w-5 h-5 animate-spin" />
                : <Download className="w-5 h-5" />}
              {exporting ? t('cust_exporting', language) : t('cust_export', language)}
            </button>
          </div>
        </div>

        {/* Real summary cards — computed over the FULL filtered set, server-side */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
              <TrendingUp className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{t('cust_summaryAvgLtv', language)}</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {formatMoney(summary.avgLtv, currency, { from: sourceCurrency })}
              </p>
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-400 shrink-0">
              <Group className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{t('cust_summaryVip', language)}</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{summary.vipCount.toLocaleString()}</p>
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 shrink-0">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{t('cust_summaryAtRisk', language)}</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{summary.atRiskCount.toLocaleString()}</p>
            </div>
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
                          {formatMoney(c.lifetime_value, currency, { exact: true, decimals: 2, from: sourceCurrency })}
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

      </div>
    </div>
  );
}
