"use client";

/**
 * Slide-in left sidebar that lists every analytics module the user can drop
 * onto their dashboard. Active during customize mode only.
 *
 * Drag-and-drop uses **native HTML5 DnD** (not @dnd-kit). We learned the hard
 * way that running two DnD systems in parallel — @dnd-kit for the sidebar
 * and react-grid-layout for the grid — meant the cursor position from the
 * @dnd-kit drop never reached RGL, so every drop landed at the end of the
 * grid (the only thing RGL knew how to do without a position hint).
 *
 * Native HTML5 DnD speaks the same `dataTransfer` protocol RGL's
 * `onDrop(layout, item, e)` callback consumes — so the sidebar marks each
 * row `draggable={true}` + writes the module_key to `dataTransfer`, RGL
 * shows a placeholder under the cursor, and on release we know exactly
 * where the user dropped.
 */

import { useState } from "react";
import { Search, X, GripVertical } from "lucide-react";

import { useUiStore } from "@/stores/uiStore";
import {
  MODULES_BY_SERIES,
  SERIES_LABELS,
  ModuleMeta,
} from "@/lib/modulesCatalog";

interface ModuleSidebarProps {
  open: boolean;
  onClose: () => void;
}

interface DraggableModuleRowProps {
  module: ModuleMeta;
}

function DraggableModuleRow({ module }: DraggableModuleRowProps) {
  const language = useUiStore((s) => s.language);
  const name = language === "ar" ? module.name_ar : module.name_en;
  const [dragging, setDragging] = useState(false);

  return (
    <li
      // ── Native HTML5 DnD source ──────────────────────────────────────
      // RGL listens for `dragstart` → `dragover` → `drop` on its grid
      // element. The custom mime type `application/x-insightx-module-key`
      // keeps us out of the way of anything else on the page that might
      // be eating generic text/plain drops.
      draggable
      onDragStart={(e) => {
        // RGL also looks at the `text/plain` payload — keep both in sync
        // so a future refactor that swaps the protocol stays working.
        e.dataTransfer.setData("module_key", module.key);
        e.dataTransfer.setData("text/plain", module.key);
        e.dataTransfer.effectAllowed = "copy";
        setDragging(true);
      }}
      onDragEnd={() => setDragging(false)}
      style={{
        opacity: dragging ? 0.5 : 1,
        touchAction: "none",
      }}
      // Mark the chip as the unified-DnD source react-grid-layout watches
      // for — RGL inspects elements with `react-grid-item="dropping"` or
      // checks for the `dropping-elem-key` data attribute when computing
      // the placeholder size during drag-over.
      data-module-key={module.key}
      className="group flex items-center gap-2 px-3 py-2 rounded-md border border-transparent hover:border-gray-200 dark:hover:border-surface-border hover:bg-gray-50 dark:hover:bg-surface-elevated cursor-grab active:cursor-grabbing transition-colors"
      title={`Drag ${module.key} onto the dashboard`}
    >
      <GripVertical className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 shrink-0" />
      <span className="font-mono text-[10px] text-slate-400 bg-gray-50 dark:bg-background-dark px-1.5 py-0.5 rounded shrink-0">
        {module.key.split("_")[0]}
      </span>
      <span className="text-xs text-gray-700 dark:text-slate-200 truncate flex-1">{name}</span>
    </li>
  );
}

export function ModuleSidebar({ open, onClose }: ModuleSidebarProps) {
  const language = useUiStore((s) => s.language);
  const [query, setQuery] = useState("");

  const seriesOrder: Array<"A" | "C" | "P"> = ["A", "C", "P"];
  const q = query.trim().toLowerCase();
  const filterFn = (m: ModuleMeta) =>
    !q ||
    m.key.toLowerCase().includes(q) ||
    m.name_en.toLowerCase().includes(q) ||
    m.name_ar.includes(query.trim());

  return (
    <>
      {/* Backdrop (only on small screens — desktop keeps the dashboard visible) */}
      {open && (
        <div
          className="fixed inset-0 bg-black/30 z-30 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-72 bg-white dark:bg-surface-card border-r border-gray-200 dark:border-surface-border shadow-lg transform transition-transform duration-300 flex flex-col ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Module catalog"
      >
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-200 dark:border-surface-border flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-gray-900 dark:text-white">
              {language === "ar" ? "إضافة تحليلات" : "Add Analytics"}
            </h2>
            <p className="text-[10px] text-slate-400 mt-0.5">
              {language === "ar"
                ? "اسحب الوحدة إلى لوحة التحكم"
                : "Drag a module onto the dashboard"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-elevated"
            aria-label="Close sidebar"
          >
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>

        {/* Search */}
        <div className="px-3 py-2 border-b border-gray-100 dark:border-surface-border">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={language === "ar" ? "ابحث..." : "Search modules..."}
              className="w-full pl-8 pr-2 py-1.5 text-xs rounded-md border border-gray-200 dark:border-surface-border bg-white dark:bg-background-dark focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>

        {/* Module groups */}
        <div className="flex-1 overflow-y-auto px-2 py-3">
          {seriesOrder.map((series) => {
            const modules = MODULES_BY_SERIES[series].filter(filterFn);
            if (modules.length === 0) return null;
            const label = SERIES_LABELS[series];
            return (
              <div key={series} className="mb-4">
                <p className="text-[10px] uppercase tracking-wider text-slate-400 px-3 mb-1">
                  {language === "ar" ? label.ar : label.en} ({modules.length})
                </p>
                <ul className="space-y-0.5">
                  {modules.map((m) => (
                    <DraggableModuleRow key={m.key} module={m} />
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </aside>
    </>
  );
}
