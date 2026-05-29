'use client';

import { useState, useEffect } from 'react';
import { Search, Database, DollarSign, AlertTriangle, Layers, Filter, Download, Sparkles, Loader2 } from 'lucide-react';
import { productsApi } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { useJobStore } from '@/stores/jobStore';
import { t } from '@/lib/i18n';
import { formatMoney } from '@/lib/format';
import type { Product } from '@/types';

const PAGE_SIZE = 25;

interface ProductsSummary {
  inventory_value: number;
  low_stock_count: number;
  categories_count: number;
}

export default function ProductsPage() {
  const language = useUiStore((s) => s.language);
  const currency = useAuthStore((s) => s.user?.preferred_currency) || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  // Filter-aware aggregates from the backend. Keeps the cards consistent with
  // whichever Tier/search filter the user picked instead of reflecting only
  // the visible 25-row page.
  const [summary, setSummary] = useState<ProductsSummary>({
    inventory_value: 0,
    low_stock_count: 0,
    categories_count: 0,
  });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [abcFilter, setAbcFilter] = useState<string | undefined>(undefined);
  const [exporting, setExporting] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // ── CSV export ───────────────────────────────────────────────────────────
  // Pull the full catalog (subject to current search/filter), render it as a
  // CSV in the browser, and trigger a download. No backend changes needed —
  // we just hit the existing list endpoint with a large page_size. The CSV
  // is RFC-4180-compliant: double-quotes around every cell, doubled internal
  // double-quotes, CRLF line endings.
  const escapeCsv = (val: unknown): string => {
    if (val === null || val === undefined) return '';
    const s = String(val);
    return `"${s.replace(/"/g, '""')}"`;
  };

  const handleExport = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      // Backend caps page_size at 100 (see backend/app/routers/products.py).
      // Asking for 10_000 was returning 422 and silently aborting the export.
      // Page through every result with the max allowed size instead — a 50k
      // catalog still finishes in ~500 small queries, but we cap iteration so
      // a runaway pages count can't hang the browser.
      const PAGE = 100;
      const MAX_PAGES = 500; // 50_000 rows upper bound, plenty for any CSV

      const firstRes = await productsApi.list({
        page: 1,
        page_size: PAGE,
        search: search || undefined,
        abc_tier: abcFilter,
        sort_by: 'total_revenue',
        sort_dir: 'desc',
      });
      const firstEnv = firstRes.data as { pages: number; items: Product[] };
      const all: Product[] = [...(firstEnv.items || [])];
      const totalPages = Math.min(firstEnv.pages ?? 1, MAX_PAGES);

      for (let p = 2; p <= totalPages; p++) {
        const r = await productsApi.list({
          page: p,
          page_size: PAGE,
          search: search || undefined,
          abc_tier: abcFilter,
          sort_by: 'total_revenue',
          sort_dir: 'desc',
        });
        const env = r.data as { items: Product[] };
        if (!env?.items?.length) break;
        all.push(...env.items);
      }

      const header = [
        'sku', 'name', 'category', 'unit_price', 'cost_price', 'stock_qty',
        'low_stock_threshold', 'abc_tier', 'return_rate', 'total_revenue',
        'total_units_sold', 'gross_margin_pct', 'is_active', 'is_low_stock',
      ];
      const rows = all.map((p) => [
        p.sku, p.name, p.category, p.unit_price, p.cost_price, p.stock_qty,
        p.low_stock_threshold, p.abc_tier ?? '', p.return_rate ?? '',
        p.total_revenue, p.total_units_sold, p.gross_margin_pct ?? '',
        p.is_active, p.is_low_stock,
      ]);

      const csv = [header, ...rows]
        .map((row) => row.map(escapeCsv).join(','))
        .join('\r\n');

      // Prepend BOM so Excel opens UTF-8 cleanly (Arabic / accented chars).
      const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const stamp = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `insightx_products_${stamp}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('[products export]', e);
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    productsApi
      .list({
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
        abc_tier: abcFilter,
        sort_by: 'total_revenue',
        sort_dir: 'desc',
      })
      .then((res) => {
        const env = res.data as {
          total: number;
          pages: number;
          items: Product[];
          summary?: ProductsSummary;
        };
        setProducts(env.items || []);
        setTotal(env.total ?? 0);
        setPages(env.pages ?? 1);
        // Cards reflect the WHOLE filtered set; backend already honored
        // current `abcFilter` and `search` when aggregating, so no extra work
        // here. Fallback to zeros keeps the UI sane if backend is older.
        if (env.summary) {
          setSummary({
            inventory_value: Number(env.summary.inventory_value) || 0,
            low_stock_count: Number(env.summary.low_stock_count) || 0,
            categories_count: Number(env.summary.categories_count) || 0,
          });
        } else {
          setSummary({ inventory_value: 0, low_stock_count: 0, categories_count: 0 });
        }
      })
      .catch((e) => {
        const msg = e?.response?.data?.detail || e?.message || 'Unknown error';
        // eslint-disable-next-line no-console
        console.error('[products] fetch failed:', e?.response?.status, msg);
        setFetchError(`${e?.response?.status ?? ''} ${msg}`.trim());
        setProducts([]);
        setTotal(0);
        setPages(1);
        setSummary({ inventory_value: 0, low_stock_count: 0, categories_count: 0 });
      })
      .finally(() => setLoading(false));
  }, [page, search, abcFilter]);

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 animate-fade-in">
      <div className="mx-auto max-w-7xl flex flex-col gap-6">
        {/* Page heading */}
        <div className="flex flex-col md:flex-row justify-between md:items-end gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">{t('prod_title', language)}</h1>
              <div className="flex items-center gap-1 rounded-full bg-purple-100 dark:bg-purple-500/10 border border-purple-200 dark:border-purple-500/20 px-2 py-0.5 text-xs font-medium text-purple-700 dark:text-purple-400">
                <Sparkles className="w-3 h-3" />
                <span>{t('prod_aiBadge', language)}</span>
              </div>
            </div>
            <p className="text-slate-500 dark:text-slate-400">
              {loading ? t('cust_loading', language) : `${total.toLocaleString()} ${t('prod_subtitle', language)}`}
            </p>
          </div>

          <div className="flex gap-3">
            <div className="w-full md:w-64 relative">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
              <input
                className="block w-full h-10 rounded-lg border border-gray-200 dark:border-surface-border bg-white dark:bg-background-dark py-2 ps-9 pe-3 text-sm text-gray-900 dark:text-white placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all"
                placeholder={t('prod_searchPlaceholder', language)}
                type="text"
                value={search}
                onChange={(e) => {
                  setPage(1);
                  setSearch(e.target.value);
                }}
              />
            </div>
          </div>
        </div>

        {/* Error banner */}
        {fetchError && (
          <div className="rounded-lg border border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-400 flex items-center gap-2">
            <span className="font-semibold">Error:</span> {fetchError}
          </div>
        )}

        {/* Stats cards — real values */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-500">
                <Database className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{t('prod_totalSkus', language)}</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{total.toLocaleString()}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-500">
                <DollarSign className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{t('prod_invValue', language)}</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {formatMoney(summary.inventory_value, currency, { from: sourceCurrency })}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-orange-100 dark:bg-orange-500/10 text-orange-600 dark:text-orange-500">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{t('prod_lowStock', language)}</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{summary.low_stock_count.toLocaleString()}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-500/10 text-purple-600 dark:text-purple-500">
                <Layers className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{t('prod_categories', language)}</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{summary.categories_count.toLocaleString()}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg bg-white dark:bg-surface-elevated border border-gray-200 dark:border-surface-border p-2 shadow-sm">
          <div className="flex items-center gap-2 px-2">
            <Filter className="w-5 h-5 text-slate-400" />
            <span className="text-sm font-medium text-gray-900 dark:text-white">{t('prod_filters', language)}</span>
            {(['A', 'B', 'C'] as const).map((tier) => (
              <button
                key={tier}
                onClick={() => {
                  setAbcFilter(abcFilter === tier ? undefined : tier);
                  setPage(1);
                }}
                className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                  abcFilter === tier
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 dark:bg-white/5 text-gray-700 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-white/10'
                }`}
              >
                Tier {tier}
              </button>
            ))}
            {abcFilter && (
              <button
                onClick={() => {
                  setAbcFilter(undefined);
                  setPage(1);
                }}
                className="rounded-md bg-gray-100 dark:bg-white/5 px-3 py-1 text-xs font-medium text-slate-500 hover:text-gray-900 dark:hover:text-white"
              >
                {t('prod_clear', language)}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2 pe-2">
            <button
              onClick={handleExport}
              disabled={exporting || products.length === 0}
              className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {exporting
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Download className="w-4 h-4" />}
              {exporting ? t('prod_exporting', language) : t('prod_export', language)}
            </button>
          </div>
        </div>

        {/* Data Table */}
        <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-start text-sm text-slate-600 dark:text-slate-300 min-w-[800px]">
              <thead className="bg-gray-50 dark:bg-surface-border/50 text-xs uppercase font-semibold text-slate-500 dark:text-slate-400 border-b border-gray-200 dark:border-surface-border">
                <tr>
                  <th className="px-6 py-4 text-start">{t('prod_thSku', language)}</th>
                  <th className="px-6 py-4 text-start">{t('prod_thName', language)}</th>
                  <th className="px-6 py-4 text-start">{t('prod_thCategory', language)}</th>
                  <th className="px-6 py-4 text-start">{t('prod_thStock', language)}</th>
                  <th className="px-6 py-4 text-end">{t('prod_thPrice', language)}</th>
                  <th className="px-6 py-4 text-end">{t('prod_thRevenue', language)}</th>
                  <th className="px-6 py-4 text-start">{t('prod_thTier', language)}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-surface-border">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-500">
                      {t('prod_loadingRow', language)}
                    </td>
                  </tr>
                ) : products.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-500">
                      {t('prod_emptyRow', language)}
                    </td>
                  </tr>
                ) : (
                  products.map((p) => (
                    <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors group">
                      <td className="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white font-mono text-xs">
                        {p.sku}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="h-8 w-8 rounded bg-gray-200 dark:bg-slate-700 flex items-center justify-center font-bold text-gray-500 dark:text-slate-400 shrink-0 text-xs">
                            {(p.sku || '??').substring(0, 2)}
                          </div>
                          <span className="text-gray-900 dark:text-white font-medium line-clamp-1">{p.name}</span>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4">{p.category}</td>
                      <td className="whitespace-nowrap px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className="text-gray-900 dark:text-white">{p.stock_qty}</span>
                          {p.is_low_stock && <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" title="Low stock"></span>}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-end text-gray-900 dark:text-white">
                        {formatMoney(p.unit_price, currency, { exact: true, decimals: 2, from: sourceCurrency })}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-end text-gray-900 dark:text-white font-medium">
                        {formatMoney(p.total_revenue, currency, { from: sourceCurrency })}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4">
                        {p.abc_tier === 'A' ? (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 dark:bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-500 border border-emerald-200 dark:border-emerald-500/20">
                            Tier A
                          </span>
                        ) : p.abc_tier === 'B' ? (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 dark:bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-500 border border-amber-200 dark:border-amber-500/20">
                            Tier B
                          </span>
                        ) : p.abc_tier === 'C' ? (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 dark:bg-slate-500/10 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:text-slate-400 border border-gray-200 dark:border-slate-500/20">
                            Tier C
                          </span>
                        ) : (
                          // Pareto's A07 only ranks products with revenue > 0; any
                          // SKU with no sales yet (zero-revenue catalog rows) lands
                          // here. We surface it as "Unranked" so the user can see
                          // why instead of an opaque dash.
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 dark:bg-slate-500/10 px-2.5 py-0.5 text-xs font-medium text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-500/20 italic">
                            {t('prod_tierUnranked', language)}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination — functional */}
          <div className="flex items-center justify-between border-t border-gray-200 dark:border-surface-border bg-gray-50 dark:bg-background-dark px-6 py-3">
            <div className="text-sm text-slate-500 dark:text-slate-400">
              {products.length === 0
                ? `0 of ${total}`
                : `${(page - 1) * PAGE_SIZE + 1}–${(page - 1) * PAGE_SIZE + products.length} of ${total.toLocaleString()}`}
            </div>
            <div className="flex items-center gap-2">
              <button
                className="rounded p-1 text-slate-400 hover:bg-gray-200 dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                {'<'}
              </button>
              <span className="text-sm text-slate-500 px-2">
                {t('prod_page', language)} {page} / {pages}
              </span>
              <button
                className="rounded p-1 text-slate-400 hover:bg-gray-200 dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
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
  );
}
