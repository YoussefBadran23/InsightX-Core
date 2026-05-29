"use client";

/**
 * Customizable dashboard grid.
 *
 * Renders the 12-column `react-grid-layout` and acts as the drop target for
 * sidebar drags. DnD uses **native HTML5** (no @dnd-kit) so RGL can read
 * the cursor position and drop the widget at the exact grid cell the user
 * released on — instead of always appending at the end.
 *
 * Flow:
 *   1. Sidebar row → `onDragStart` writes `module_key` to dataTransfer.
 *   2. User drags over the grid → RGL renders a placeholder under cursor.
 *   3. User releases → RGL fires `onDrop(layout, item, e)` with the cell
 *      coordinates; we read `module_key` from dataTransfer and call
 *      `addWidgetAt(module_key, item.x, item.y)`.
 */

import { useCallback, useMemo, useState } from "react";
import { Responsive, WidthProvider, Layout } from "react-grid-layout";
import { Sparkles, PackagePlus } from "lucide-react";

import { useDashboardStore, DashboardWidget } from "@/stores/dashboardStore";
import { useUiStore } from "@/stores/uiStore";

import { ChartCard } from "@/components/charts/ChartCard";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

const ResponsiveGrid = WidthProvider(Responsive);

interface CustomizableDashboardProps {
  jobId: string | null;
  /**
   * Optional pre-fetched analytics modules dict, keyed by module_key. When
   * supplied, each `<ChartCard>` skips its own /analytics/summary call and
   * renders the slice directly — collapsing N+1 fetches into a single
   * upstream request owned by the Analytics page.
   *
   * Pass `undefined` to keep the legacy per-card fetch behaviour (used
   * anywhere outside the Analytics page).
   */
  analyticsModules?: Record<string, unknown> | null;
}

export function CustomizableDashboard({ jobId, analyticsModules }: CustomizableDashboardProps) {
  const language = useUiStore((s) => s.language);
  const widgets = useDashboardStore((s) => s.widgets);
  const isCustomizing = useDashboardStore((s) => s.isCustomizing);
  const updateLayout = useDashboardStore((s) => s.updateLayout);
  const addWidgetAt = useDashboardStore((s) => s.addWidgetAt);

  // Visual highlight when something is being dragged over the grid. Mirrors
  // the old @dnd-kit `isOver` ring so the drop target reads obviously.
  const [isOver, setIsOver] = useState(false);

  // Caller is in "single-fetch" mode if it gave us a modules dict (even an
  // empty one). When `analyticsModules === undefined` we degrade gracefully:
  // ChartCard does its own per-widget fetch.
  const hasPreload = analyticsModules !== undefined && analyticsModules !== null;

  // Convert widgets into react-grid-layout's expected shape.
  // We generate separate responsive layouts so charts never overflow on
  // mobile (xs) or tiny (xxs) screens — RGL doesn't auto-clamp widget
  // widths to the column count, so we do it explicitly per breakpoint.
  const { lgLayout, mdLayout, smLayout, xsLayout, xxsLayout } = useMemo(() => {
    const base = widgets.map((w) => ({
      i: w.id,
      x: w.x,
      y: w.y,
      w: w.w,
      h: w.h,
      minW: 3,
      minH: 3,
    }));

    // sm (768px, 8 cols): keep width but cap at 8
    const sm = base.map((item) => ({ ...item, w: Math.min(item.w, 8), minW: 2 }));

    // xs (480px, 4 cols): full-width single column, stacked vertically
    let xsY = 0;
    const xs = base.map((item) => {
      const row = { ...item, x: 0, y: xsY, w: 4, h: item.h, minW: 4, minH: 3 };
      xsY += item.h;
      return row;
    });

    // xxs (0px, 2 cols): full-width, same stack order
    let xxsY = 0;
    const xxs = base.map((item) => {
      const row = { ...item, x: 0, y: xxsY, w: 2, h: item.h, minW: 2, minH: 3 };
      xxsY += item.h;
      return row;
    });

    return { lgLayout: base, mdLayout: base, smLayout: sm, xsLayout: xs, xxsLayout: xxs };
  }, [widgets]);

  const handleLayoutChange = useCallback(
    (newLayout: Layout[]) => {
      // Skip the spurious initial layout-change RGL fires on mount when
      // widgets are empty — avoids overwriting a freshly-persisted layout.
      if (newLayout.length === 0 && widgets.length === 0) return;

      // Merge new positions back into our widgets, preserving module_key.
      const next: DashboardWidget[] = newLayout.map((item) => {
        const existing = widgets.find((w) => w.id === item.i);
        return {
          id: item.i,
          module_key: existing?.module_key || "",
          x: item.x,
          y: item.y,
          w: item.w,
          h: item.h,
        };
      });
      updateLayout(next);
    },
    [widgets, updateLayout],
  );

  // ── Native HTML5 drop wiring ─────────────────────────────────────────
  // RGL fires `onDrop(layout, item, e)` once the user releases over the
  // grid. `item.x` / `item.y` are the grid coordinates of the placeholder
  // at the release moment. We grab the `module_key` from `dataTransfer`
  // (set by ModuleSidebar's onDragStart) and push the widget exactly
  // where the cursor landed.
  const handleDrop = useCallback(
    (_layout: Layout[], item: Layout, e: any) => {
      try {
        const moduleKey =
          e?.dataTransfer?.getData("module_key") ||
          e?.dataTransfer?.getData("text/plain");
        if (!moduleKey) return;
        addWidgetAt(moduleKey, item.x, item.y);
      } finally {
        setIsOver(false);
      }
    },
    [addWidgetAt],
  );

  return (
    <div
      // The outer wrapper takes care of the visual "is over" highlight
      // because RGL's own onDragOver doesn't propagate up reliably across
      // browsers. We listen ourselves and let RGL still handle placement.
      className={`relative w-full transition-colors rounded-xl ${
        isOver ? "ring-2 ring-primary ring-offset-2 bg-primary/5" : ""
      }`}
      onDragOver={(e) => {
        if (e.dataTransfer?.types?.includes("module_key")) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
          if (!isOver) setIsOver(true);
        }
      }}
      onDragLeave={() => setIsOver(false)}
      onDrop={() => setIsOver(false)}
    >
      {widgets.length === 0 ? (
        <EmptyDashboard customizing={isCustomizing} language={language} />
      ) : (
        <ResponsiveGrid
          className="layout"
          layouts={{ lg: lgLayout, md: mdLayout, sm: smLayout, xs: xsLayout, xxs: xxsLayout }}
          breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
          cols={{ lg: 12, md: 12, sm: 8, xs: 4, xxs: 2 }}
          rowHeight={60}
          margin={[12, 12]}
          containerPadding={[0, 0]}
          isDraggable={isCustomizing}
          isResizable={isCustomizing}
          // ── RGL native drop ─────────────────────────────────────────
          isDroppable={isCustomizing}
          droppingItem={{ i: "__dropping__", w: 6, h: 5 }}
          onDrop={handleDrop}
          // Only persist layout changes from the large (lg/md) breakpoint.
          // On xs/xxs we use a fixed single-column stack that shouldn't
          // overwrite the desktop positions the user arranged.
          onLayoutChange={(_layout, allLayouts) => {
            const lgBreak = allLayouts.lg;
            if (lgBreak && lgBreak.length > 0) handleLayoutChange(lgBreak);
          }}
          draggableCancel=".no-drag"
          useCSSTransforms
          preventCollision={false}
          compactType="vertical"
        >
          {widgets.map((w) => (
            <div key={w.id} className="overflow-hidden" style={{ contain: 'layout style paint' }}>
              <ChartCard
                widgetId={w.id}
                moduleKey={w.module_key}
                jobId={jobId}
                // Slice the parent's pre-fetched modules per widget. Pass
                // `undefined` (no prop spread) when no preload is available
                // so ChartCard falls back to its own fetch.
                {...(hasPreload
                  ? { preloadedData: (analyticsModules as Record<string, unknown>)[w.module_key] ?? null }
                  : {})}
              />
            </div>
          ))}
        </ResponsiveGrid>
      )}
    </div>
  );
}

function EmptyDashboard({ customizing, language }: { customizing: boolean; language: string }) {
  return (
    <div className="border-2 border-dashed border-gray-200 dark:border-surface-border rounded-xl py-16 px-6 text-center">
      {customizing ? (
        <>
          <PackagePlus className="w-12 h-12 text-primary mx-auto mb-3 opacity-70" />
          <p className="text-gray-700 dark:text-slate-200 font-medium">
            {language === "ar"
              ? "اسحب وحدة من الشريط الجانبي إلى هنا"
              : "Drag a module from the sidebar to drop it here"}
          </p>
          <p className="text-xs text-slate-400 mt-1">
            {language === "ar"
              ? "يمكنك إعادة ترتيب وتغيير حجم البطاقات بعد إضافتها"
              : "You can rearrange and resize cards once added"}
          </p>
        </>
      ) : (
        <>
          <Sparkles className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-gray-700 dark:text-slate-200 font-medium">
            {language === "ar" ? "لوحة التحكم فارغة" : "Your dashboard is empty"}
          </p>
          <p className="text-xs text-slate-400 mt-1">
            {language === "ar"
              ? 'انقر "تخصيص لوحة التحكم" لإضافة بطاقات'
              : 'Click "Customize Dashboard" to add charts'}
          </p>
        </>
      )}
    </div>
  );
}
