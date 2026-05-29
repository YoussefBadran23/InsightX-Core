"use client";

/**
 * Per-chart export dropdown.
 *
 * Renders a kebab button on the chart card. Clicking opens a small menu with
 * "Export CSV" and "Export JSON". Both are pure client-side blob downloads —
 * no backend round-trip required.
 *
 *   CSV  →  flattens the first array-of-objects in the module's result_json
 *           (e.g. `by_channel`, `top_customers`, `hot_products`). Falls back
 *           to a single-row dump of `summary` if no array exists.
 *   JSON →  raw module result_json verbatim.
 *
 * The kebab is intentionally `no-drag` so react-grid-layout's drag handlers
 * don't eat the click during Customize Mode.
 */

import { useEffect, useRef, useState } from "react";
import { MoreVertical, FileText, FileJson } from "lucide-react";

interface ChartExportMenuProps {
  /** The analytics result JSON for this chart (`data` prop on every chart). */
  data: unknown;
  /** Module key — used as the download filename stem. */
  moduleKey: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function findPrimaryArray(data: any): { key: string; rows: any[] } | null {
  if (!data || typeof data !== "object") return null;

  // Common analytics-module array shapes, in preference order. Keys earlier
  // in this list win when multiple arrays exist on the same module — e.g.
  // for A14 we want `by_channel` over `monthly_acquisition`.
  const PREFERRED_KEYS = [
    "by_channel", "by_status", "by_category", "by_country", "by_region",
    "by_segment", "by_product", "by_brand", "by_tier", "by_sentiment",
    "top_customers", "top_products", "top_by_revenue", "top_by_orders",
    "top_by_aov", "top_by_quantity", "top_by_margin",
    "hot_products", "critical_products", "all_products",
    "top_at_risk", "top_pairs", "anomalies",
    "by_brand", "products", "segments", "rows", "items",
  ];
  for (const k of PREFERRED_KEYS) {
    const v = (data as Record<string, unknown>)[k];
    if (Array.isArray(v) && v.length > 0 && typeof v[0] === "object") {
      return { key: k, rows: v };
    }
  }

  // Fallback: pick the largest array-of-objects on the top level.
  let best: { key: string; rows: any[] } | null = null;
  for (const [k, v] of Object.entries(data)) {
    if (Array.isArray(v) && v.length > 0 && typeof v[0] === "object") {
      if (!best || v.length > best.rows.length) {
        best = { key: k, rows: v as any[] };
      }
    }
  }
  return best;
}

function toCsvBlob(data: unknown): { blob: Blob; sheetKey: string } {
  const primary = findPrimaryArray(data);
  let rows: any[];
  let sheetKey = "data";
  if (primary) {
    rows = primary.rows;
    sheetKey = primary.key;
  } else if (data && typeof data === "object" && "summary" in (data as object)) {
    rows = [(data as any).summary];
    sheetKey = "summary";
  } else {
    rows = [data];
  }

  if (!rows.length) {
    return { blob: new Blob([""], { type: "text/csv;charset=utf-8" }), sheetKey };
  }

  // Union of all keys across rows — handles modules where some rows have
  // optional fields the others don't.
  const headers = Array.from(
    new Set(
      rows.flatMap((r) =>
        r && typeof r === "object" ? Object.keys(r) : ["value"],
      ),
    ),
  );

  const escapeCsv = (v: unknown): string => {
    if (v == null) return "";
    if (typeof v === "object") return `"${JSON.stringify(v).replace(/"/g, '""')}"`;
    return `"${String(v).replace(/"/g, '""')}"`;
  };

  const lines = [
    headers.join(","),
    ...rows.map((r) =>
      headers.map((h) =>
        escapeCsv(r && typeof r === "object" ? (r as Record<string, unknown>)[h] : r),
      ).join(","),
    ),
  ];
  // BOM so Excel opens UTF-8 correctly without prompting.
  return {
    blob: new Blob(["﻿" + lines.join("\r\n")], {
      type: "text/csv;charset=utf-8",
    }),
    sheetKey,
  };
}

function toJsonBlob(data: unknown): Blob {
  return new Blob([JSON.stringify(data ?? null, null, 2)], {
    type: "application/json;charset=utf-8",
  });
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Defer revoke so the click triggers the download in older browsers
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

// ── Component ──────────────────────────────────────────────────────────────

export function ChartExportMenu({ data, moduleKey }: ChartExportMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Close on outside-click. We attach to `mousedown` (not `click`) so a click
  // that toggles the menu doesn't fire close-then-open in a single tick.
  useEffect(() => {
    if (!open) return;
    function onDocMouseDown(e: MouseEvent) {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [open]);

  const handleExportCsv = () => {
    const { blob, sheetKey } = toCsvBlob(data);
    downloadBlob(blob, `${moduleKey}-${sheetKey}.csv`);
    setOpen(false);
  };

  const handleExportJson = () => {
    downloadBlob(toJsonBlob(data), `${moduleKey}.json`);
    setOpen(false);
  };

  return (
    <div
      ref={rootRef}
      className="no-drag absolute top-2 right-2 z-40"
      onClick={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className="p-1 rounded-md bg-white/80 dark:bg-surface-elevated/80 backdrop-blur border border-gray-200/60 dark:border-white/10 text-slate-500 hover:text-gray-900 dark:hover:text-white opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity shadow-sm cursor-pointer"
        aria-label="Chart options"
        aria-haspopup="menu"
        aria-expanded={open}
        title="Export"
      >
        <MoreVertical className="w-3.5 h-3.5" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute top-full right-0 mt-1 w-44 rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-surface-card shadow-xl py-1 z-50"
        >
          <button
            type="button"
            onClick={handleExportCsv}
            role="menuitem"
            className="w-full text-left flex items-center gap-2 px-3 py-1.5 text-[12px] text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-surface-elevated transition-colors cursor-pointer"
          >
            <FileText className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
            Export as CSV
          </button>
          <button
            type="button"
            onClick={handleExportJson}
            role="menuitem"
            className="w-full text-left flex items-center gap-2 px-3 py-1.5 text-[12px] text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-surface-elevated transition-colors cursor-pointer"
          >
            <FileJson className="w-3.5 h-3.5 text-amber-500 shrink-0" />
            Export as JSON
          </button>
        </div>
      )}
    </div>
  );
}
