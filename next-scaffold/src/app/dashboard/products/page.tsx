'use client';

import { useState, useEffect } from 'react';
import { Search, Plus, Database, DollarSign, AlertTriangle, Layers, Filter, Download, MoreVertical, Sparkles } from 'lucide-react';
import { productsApi } from '@/lib/api';
import type { ProductInsight } from '@/types';

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    productsApi.list({ page: 0, page_size: 50 }).then((res) => {
      setProducts(res.data);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 animate-fade-in">
      <div className="mx-auto max-w-7xl flex flex-col gap-6">
        
        {/* Page Heading View Header equivalent */}
        <div className="flex flex-col md:flex-row justify-between md:items-end gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">Product Inventory</h1>
              <div className="flex items-center gap-1 rounded-full bg-purple-100 dark:bg-purple-500/10 border border-purple-200 dark:border-purple-500/20 px-2 py-0.5 text-xs font-medium text-purple-700 dark:text-purple-400">
                <Sparkles className="w-3 h-3" />
                <span>AI Extracted</span>
              </div>
            </div>
            <p className="text-slate-500 dark:text-slate-400">Manage and track your retail product catalog with automated insights.</p>
          </div>

          <div className="flex gap-3">
             <div className="w-full md:w-64 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                <input 
                  className="block w-full h-10 rounded-lg border border-gray-200 dark:border-surface-border bg-white dark:bg-background-dark py-2 pl-9 pr-3 text-sm text-gray-900 dark:text-white placeholder-slate-400 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all" 
                  placeholder="Search inventory, SKUs..." 
                  type="text"
                />
            </div>
            <button className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover transition-colors shadow-lg shadow-primary/20 shrink-0">
              <Plus className="w-4 h-4" />
              <span>Add Product</span>
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-500">
                <Database className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Total SKUs</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">450</p>
              </div>
            </div>
          </div>
          
          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-500">
                <DollarSign className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Inventory Value</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">$85,000</p>
              </div>
            </div>
          </div>
          
          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-orange-100 dark:bg-orange-500/10 text-orange-600 dark:text-orange-500">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Low Stock Items</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">12</p>
              </div>
            </div>
          </div>
          
          <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated p-5 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-500/10 text-purple-600 dark:text-purple-500">
                <Layers className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Categories</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">8</p>
              </div>
            </div>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg bg-white dark:bg-surface-elevated border border-gray-200 dark:border-surface-border p-2 shadow-sm">
          <div className="flex items-center gap-2 px-2">
            <Filter className="w-5 h-5 text-slate-400" />
            <span className="text-sm font-medium text-gray-900 dark:text-white">Filters:</span>
            <button className="rounded-md bg-gray-100 dark:bg-white/5 px-3 py-1 text-sm font-medium text-gray-700 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-white/10 transition-colors">
              Category: All
            </button>
            <button className="rounded-md bg-gray-100 dark:bg-white/5 px-3 py-1 text-sm font-medium text-gray-700 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-white/10 transition-colors">
              Status: Active
            </button>
          </div>
          <div className="flex items-center gap-2 pr-2">
            <button className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-gray-900 dark:hover:text-white transition-colors">
              <Download className="w-4 h-4" />
              Export
            </button>
          </div>
        </div>

        {/* Data Table */}
        <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-elevated shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600 dark:text-slate-300 min-w-[800px]">
              <thead className="bg-gray-50 dark:bg-surface-border/50 text-xs uppercase font-semibold text-slate-500 dark:text-slate-400 border-b border-gray-200 dark:border-surface-border">
                <tr>
                  <th className="px-6 py-4">Product SKU</th>
                  <th className="px-6 py-4">Product Name</th>
                  <th className="px-6 py-4">Category</th>
                  <th className="px-6 py-4">Stock Limit Info</th>
                  <th className="px-6 py-4">Unit Price</th>
                  <th className="px-6 py-4">ABC Tier Status</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-surface-border">
                {loading ? (
                  <tr>
                     <td colSpan={7} className="p-8 text-center text-slate-500">Loading products...</td>
                  </tr>
                ) : products.length === 0 ? (
                  <tr>
                     <td colSpan={7} className="p-8 text-center text-slate-500">No products found. Add a product to get started.</td>
                  </tr>
                ) : (
                  products.map((p) => {
                    const isLowStock = false; // Could compute based on threshold if available
                    return (
                      <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors group">
                        <td className="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white">{p.sku}</td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="h-8 w-8 rounded bg-gray-200 dark:bg-slate-700 flex items-center justify-center font-bold text-gray-500 dark:text-slate-400 shrink-0">
                              {p.sku.substring(0, 2)}
                            </div>
                            <span className="text-gray-900 dark:text-white font-medium line-clamp-1">{p.product_name}</span>
                          </div>
                        </td>
                        <td className="whitespace-nowrap px-6 py-4">{p.category}</td>
                        <td className="whitespace-nowrap px-6 py-4">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-900 dark:text-white">{p.stock_level}</span>
                            {isLowStock && <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse"></span>}
                          </div>
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-gray-900 dark:text-white">${p.unit_price?.toFixed(2)}</td>
                        <td className="whitespace-nowrap px-6 py-4">
                          {p.abc_class === 'A' ? (
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 dark:bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-500 border border-emerald-200 dark:border-emerald-500/20">
                              Tier A (High Value)
                            </span>
                          ) : p.abc_class === 'B' ? (
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 dark:bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-500 border border-amber-200 dark:border-amber-500/20">
                              Tier B
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 dark:bg-slate-500/10 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:text-slate-400 border border-gray-200 dark:border-slate-500/20">
                              Tier C
                            </span>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-right">
                          <button className="text-slate-400 hover:text-gray-900 dark:hover:text-white transition-colors cursor-pointer">
                            <MoreVertical className="w-5 h-5 mx-auto" />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          
          {/* Table Footer / Pagination */}
          <div className="flex items-center justify-between border-t border-gray-200 dark:border-surface-border bg-gray-50 dark:bg-background-dark px-6 py-3">
            <div className="text-sm text-slate-500 dark:text-slate-400">
              Showing <span className="font-medium text-gray-900 dark:text-white">1</span> to <span className="font-medium text-gray-900 dark:text-white">{Math.min(products.length, 5)}</span> of <span className="font-medium text-gray-900 dark:text-white">{Math.max(products.length, 450)}</span> results
            </div>
            <div className="flex items-center gap-2">
              <button className="rounded p-1 text-slate-400 hover:bg-gray-200 dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-white disabled:opacity-50 transition-colors cursor-pointer" disabled>
                 {'<'}
              </button>
              <button className="rounded p-1 text-slate-400 hover:bg-gray-200 dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-white transition-colors cursor-pointer">
                 {'>'}
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
