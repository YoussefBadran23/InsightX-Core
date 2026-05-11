'use client';

import { useState, useEffect, useMemo } from 'react';
import { Search, Plus, Database, DollarSign, AlertTriangle, Layers, Filter, Download, MoreVertical, Sparkles } from 'lucide-react';
import { productsApi } from '@/lib/api';
import { useUiStore } from '@/stores/uiStore';
import { t } from '@/lib/i18n';
import type { Product } from '@/types';

const PAGE_SIZE = 25;

export default function ProductsPage() {
  const language = useUiStore((s) => s.language);
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [abcFilter, setAbcFilter] = useState<string | undefined>(undefined);

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
        const env = res.data as { total: number; pages: number; items: Product[] };
        setProducts(env.items || []);
        setTotal(env.total ?? 0);
        setPages(env.pages ?? 1);
      })
      .catch(() => {
        setProducts([]);
        setTotal(0);
        setPages(1);
      })
      .finally(() => setLoading(false));
  }, [page, search, abcFilter]);

  // Real stats card metrics derived from current page
  const stats = useMemo(() => {
    if (products.length === 0) {
      return { invValue: 0, lowStock: 0, categories: 0 };
    }
    const invValue = products.reduce((sum, p) => sum + Number(p.unit_price || 0) * Number(p.stock_qty || 0), 0);
    const lowStock = products.filter((p) => p.is_low_stock).length;
    const categories = new Set(products.map((p) => p.category)).size;
    return { invValue, lowStock, categories };
  }, [products]);

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
            <button className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover transition-colors shadow-lg shadow-primary/20 shrink-0">
              <Plus className="w-4 h-4" />
              <span>{t('prod_addProduct', language)}</span>
            </button>
          </div>
        </div>

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
                  ${Math.round(stats.invValue).toLocaleString()}
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
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.lowStock}</p>
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
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.categories}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg bg-white dark:bg-surface-elevated border border-gray-200 dark:border-surface-border p-2 shadow-sm">
          <div className="flex items-center gap-2 px-2">
            <Filter className="w-5 h-5 text-slate-400" />
            <span className="text-sm font-medium text-gray-900 dark:text-white">{t('prod_filters', language)}</span>
            {(['A', 'B', 'C'] as const).map((t) => (
              <button
                key={t}
                onClick={() => {
                  setAbcFilter(abcFilter === t ? undefined : t);
                  setPage(1);
                }}
                className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                  abcFilter === t
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 dark:bg-white/5 text-gray-700 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-white/10'
                }`}
              >
                Tier {t}
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
            <button className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white transition-colors">
              <Download className="w-4 h-4" />
              Export
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
                  <th className="px-6 py-4 text-end">{t('prod_thActions', language)}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-surface-border">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="p-8 text-center text-slate-500">
                      {t('prod_loadingRow', language)}
                    </td>
                  </tr>
                ) : products.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-8 text-center text-slate-500">
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
                        ${Number(p.unit_price).toFixed(2)}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-end text-gray-900 dark:text-white font-medium">
                        ${Number(p.total_revenue).toLocaleString(undefined, { maximumFractionDigits: 0 })}
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
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-end">
                        <button className="text-slate-400 hover:text-gray-900 dark:hover:text-white transition-colors cursor-pointer">
                          <MoreVertical className="w-5 h-5 mx-auto" />
                        </button>
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
