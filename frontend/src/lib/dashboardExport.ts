/**
 * Dashboard-level export helpers.
 *
 * Two flows:
 *
 *   - exportAnalyticsToExcel(modules)   →  one .xlsx workbook with one sheet
 *                                          per analytics module (whichever
 *                                          array is the module's "main" rows,
 *                                          plus a "Summary" sheet at the top).
 *
 *   - exportElementToPdf(node, opts)    →  html2canvas-snapshots the DOM node
 *                                          and writes it as a single-page PDF
 *                                          via jsPDF. Used to capture the
 *                                          rendered analytics grid as-is.
 *
 * Both run entirely client-side — no backend round trip. The functions are
 * loaded dynamically (`await import(...)`) so the heavy xlsx / jspdf bundles
 * don't pollute every page's first-load JS.
 */

// ── Pick the "primary" array from a module's result_json ─────────────────────

const PREFERRED_KEYS = [
  "by_channel", "by_status", "by_category", "by_country", "by_region",
  "by_segment", "by_product", "by_brand", "by_tier", "by_sentiment",
  "top_customers", "top_products", "top_by_revenue", "top_by_orders",
  "top_by_aov", "top_by_quantity", "top_by_margin",
  "hot_products", "critical_products", "all_products",
  "top_at_risk", "top_pairs", "anomalies",
  "segments", "products", "rows", "items",
];

function findPrimaryArray(data: any): { key: string; rows: any[] } | null {
  if (!data || typeof data !== "object") return null;
  for (const k of PREFERRED_KEYS) {
    const v = data[k];
    if (Array.isArray(v) && v.length > 0 && typeof v[0] === "object") {
      return { key: k, rows: v };
    }
  }
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

/** Coerce a single value into something a spreadsheet cell can hold. */
function flattenCell(v: unknown): unknown {
  if (v == null) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return v;
}

/** Excel sheet names are capped at 31 chars and can't contain []*?:/\. */
function safeSheetName(name: string): string {
  const cleaned = name.replace(/[[\]*?:/\\]/g, "").trim() || "sheet";
  return cleaned.slice(0, 31);
}

// ── Excel export ─────────────────────────────────────────────────────────────

export interface ExcelExportOptions {
  /** Filename without extension. Default: `insightx_dashboard_<date>`. */
  filename?: string;
}

/**
 * Compile the {module_key → result_json} dict into a single .xlsx workbook
 * and trigger a browser download.
 *
 *   - Sheet 1: "Summary" — one row per module with its top-level summary.* fields
 *   - Sheets 2..N: one per module with rows from its primary array
 *
 * Module sheets are skipped if the module has no array data (e.g. the
 * worker only returned a `summary` block). Those modules still appear in
 * the Summary sheet so the export captures the full picture.
 */
export async function exportAnalyticsToExcel(
  modules: Record<string, any>,
  opts: ExcelExportOptions = {},
): Promise<void> {
  // Dynamic import: keeps xlsx out of the analytics page's initial bundle.
  const XLSX = await import("xlsx");
  const wb = XLSX.utils.book_new();

  // ── Summary sheet (one row per module) ─────────────────────────────────
  const summaryRows: Record<string, unknown>[] = [];
  for (const [moduleKey, data] of Object.entries(modules || {})) {
    if (!data || typeof data !== "object") continue;
    const sum = (data as any).summary || {};
    const headline = (data as any).headline || {};
    summaryRows.push({
      module_key: moduleKey,
      question: (data as any).question ?? "",
      headline_value: headline.value ?? "",
      headline_label: headline.label ?? "",
      headline_trend_pct: headline.trend_pct ?? "",
      ...Object.fromEntries(
        Object.entries(sum).map(([k, v]) => [`summary.${k}`, flattenCell(v)]),
      ),
    });
  }
  if (summaryRows.length > 0) {
    const ws = XLSX.utils.json_to_sheet(summaryRows);
    XLSX.utils.book_append_sheet(wb, ws, "Summary");
  }

  // ── Per-module sheets ──────────────────────────────────────────────────
  const usedNames = new Set<string>(["Summary"]);
  for (const [moduleKey, data] of Object.entries(modules || {})) {
    const primary = findPrimaryArray(data);
    if (!primary) continue;
    const rows = primary.rows.map((r) =>
      Object.fromEntries(
        Object.entries(r as Record<string, unknown>).map(([k, v]) => [k, flattenCell(v)]),
      ),
    );
    if (rows.length === 0) continue;

    // Resolve sheet-name collisions by appending a 2-digit suffix
    let name = safeSheetName(moduleKey);
    let n = 2;
    while (usedNames.has(name)) {
      name = safeSheetName(`${moduleKey}_${n}`);
      n += 1;
    }
    usedNames.add(name);

    const ws = XLSX.utils.json_to_sheet(rows);
    XLSX.utils.book_append_sheet(wb, ws, name);
  }

  if (wb.SheetNames.length === 0) {
    // Fallback: at least one sheet so the file isn't invalid
    const ws = XLSX.utils.aoa_to_sheet([["No module data available"]]);
    XLSX.utils.book_append_sheet(wb, ws, "Empty");
  }

  const stamp = new Date().toISOString().slice(0, 10);
  const filename = `${opts.filename || "insightx_dashboard"}_${stamp}.xlsx`;
  XLSX.writeFile(wb, filename);
}

// ── PDF export ───────────────────────────────────────────────────────────────

export interface PdfExportOptions {
  /** Filename without extension. */
  filename?: string;
  /** Background colour to render the snapshot on. Default: white. */
  backgroundColor?: string;
}

/**
 * Snapshot a DOM node and download it as a PDF.
 *
 * The page size is computed from the captured canvas's aspect ratio so the
 * dashboard's layout isn't squished into Letter/A4. Pixel-density is 2× for
 * crisp text on high-DPI displays.
 */
export async function exportElementToPdf(
  node: HTMLElement,
  opts: PdfExportOptions = {},
): Promise<void> {
  const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
    import("html2canvas"),
    import("jspdf"),
  ]);

  const canvas = await html2canvas(node, {
    scale: 2,
    backgroundColor: opts.backgroundColor ?? "#ffffff",
    useCORS: true,
    logging: false,
    // Letting html2canvas use the element's own size avoids weird viewport
    // clipping when the user scrolled mid-page before exporting.
    windowWidth: node.scrollWidth,
    windowHeight: node.scrollHeight,
  });

  const widthPx = canvas.width;
  const heightPx = canvas.height;

  // jsPDF works in points by default. 1 px ≈ 0.75 pt at 96dpi, but we
  // scaled the canvas 2×, so we divide back down. Result: PDF matches
  // the rendered pixel dimensions one-for-one.
  const widthPt = widthPx / 2;
  const heightPt = heightPx / 2;
  const orientation = widthPt >= heightPt ? "landscape" : "portrait";

  const pdf = new jsPDF({
    orientation,
    unit: "pt",
    format: [widthPt, heightPt],
    compress: true,
  });

  const imgData = canvas.toDataURL("image/png", 0.92);
  pdf.addImage(imgData, "PNG", 0, 0, widthPt, heightPt);

  const stamp = new Date().toISOString().slice(0, 10);
  pdf.save(`${opts.filename || "insightx_dashboard"}_${stamp}.pdf`);
}
