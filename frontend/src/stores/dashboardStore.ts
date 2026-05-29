/**
 * Dashboard layout store — per-user customization persisted to localStorage.
 *
 * Each "widget" represents one analytics module rendered as a chart card. The
 * widget owns its position (x, y) and size (w, h) on a 12-column grid that
 * `react-grid-layout` interprets. The store is intentionally thin — it
 * doesn't fetch data; the chart components do that based on `module_key`.
 *
 * Default-dashboard seeding
 * -------------------------
 * On a user's first visit we pre-populate the grid with ALL 39 catalog
 * modules so they see every chart immediately. The `initialized` flag is
 * persisted so we don't re-seed if the user later empties the dashboard
 * intentionally.
 *
 * We persist to localStorage rather than the backend for now. Switching to a
 * backend-persisted layout later is a single endpoint swap + a rehydration
 * call from the layout effect — the rest of the surface stays the same.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import { MODULES_BY_KEY, MODULES_CATALOG } from "@/lib/modulesCatalog";

export interface DashboardWidget {
  id: string;          // unique per drop (so user can drop the same module twice if they want)
  module_key: string;  // matches MODULES_CATALOG.key
  x: number;
  y: number;
  w: number;
  h: number;
}

interface DashboardState {
  widgets: DashboardWidget[];
  isCustomizing: boolean;
  /** True once seedDefaultDashboard() has run for this user. Persisted so
   *  emptying the dashboard doesn't trigger a re-seed on the next page load. */
  initialized: boolean;
  /**
   * The "committed" layout — what Save Layout snapshotted. Home page reads
   * this so an in-progress edit doesn't leak into the home dashboard until
   * the user explicitly saves. Defaults to the same as `widgets` so a user
   * who never opens customize mode still gets a sane home view.
   */
  savedWidgets: DashboardWidget[];
  /**
   * Snapshot taken when customize mode opens, so Cancel can revert without
   * losing the previously-saved layout. Cleared on save / cancel.
   */
  draftSnapshot: DashboardWidget[] | null;

  toggleCustomizing: () => void;
  addWidget: (module_key: string) => void;
  /**
   * Drop a widget at the exact grid cell (x, y) the user released on.
   * Used by react-grid-layout's native HTML5 drop API — we replaced the
   * old @dnd-kit setup that always appended at the end of the grid.
   */
  addWidgetAt: (module_key: string, x: number, y: number) => void;
  removeWidget: (id: string) => void;
  updateLayout: (next: DashboardWidget[]) => void;
  resetLayout: () => void;
  /** Commit the current `widgets` as the saved layout. Closes customize mode. */
  saveLayout: () => void;
  /** Revert to the snapshot taken when customize mode opened. */
  cancelLayout: () => void;
  /** Seed the dashboard with all 39 modules in a tidy 2-column packed layout. */
  seedDefaultDashboard: () => void;
}

// Spawn position helper: place new widgets at the next vacant row so they
// don't overlap existing ones. react-grid-layout will pack them down on
// the next layout pass, but starting from below avoids visual flash.
function nextSpawnY(widgets: DashboardWidget[]): number {
  if (widgets.length === 0) return 0;
  return Math.max(...widgets.map((w) => w.y + w.h));
}

/**
 * Two-column shelf packer. Half-width charts (default_w ≤ 6) alternate
 * between the left and right columns; wider charts (default_w ≥ 8) span
 * the full row. Both columns advance independently so we never leave a
 * vertical gap on either side.
 */
function buildDefaultLayout(): DashboardWidget[] {
  const widgets: DashboardWidget[] = [];
  let leftY = 0;
  let rightY = 0;

  MODULES_CATALOG.forEach((m, i) => {
    const id = `${m.key}-default-${i}`;
    if (m.default_w >= 8) {
      // Full-width row: align both columns then add a wide widget.
      const y = Math.max(leftY, rightY);
      widgets.push({
        id, module_key: m.key, x: 0, y, w: m.default_w, h: m.default_h,
      });
      leftY = y + m.default_h;
      rightY = y + m.default_h;
    } else {
      // Half-width: pack into the shorter column. Normalise to width=6 so
      // the two columns line up perfectly on initial render.
      if (leftY <= rightY) {
        widgets.push({
          id, module_key: m.key, x: 0, y: leftY, w: 6, h: m.default_h,
        });
        leftY += m.default_h;
      } else {
        widgets.push({
          id, module_key: m.key, x: 6, y: rightY, w: 6, h: m.default_h,
        });
        rightY += m.default_h;
      }
    }
  });

  return widgets;
}

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set, get) => ({
      widgets: [],
      isCustomizing: false,
      initialized: false,
      savedWidgets: [],
      draftSnapshot: null,

      toggleCustomizing: () => set((s) => {
        // Opening → snapshot the current widgets so Cancel can revert.
        // Closing without explicit save/cancel → behaves like cancel (revert).
        if (!s.isCustomizing) {
          return { isCustomizing: true, draftSnapshot: [...s.widgets] };
        }
        return {
          isCustomizing: false,
          widgets: s.draftSnapshot ?? s.widgets,
          draftSnapshot: null,
        };
      }),

      addWidget: (module_key: string) => {
        const meta = MODULES_BY_KEY[module_key];
        if (!meta) {
          // Unknown module key — log and bail rather than crashing the UI.
          // This branch fires if someone deletes a module from the catalog
          // but a stale localStorage entry still references it.
          // eslint-disable-next-line no-console
          console.warn(`[dashboardStore] unknown module_key: ${module_key}`);
          return;
        }
        const widgets = get().widgets;
        const newWidget: DashboardWidget = {
          id: `${module_key}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          module_key,
          x: 0,
          y: nextSpawnY(widgets),
          w: meta.default_w,
          h: meta.default_h,
        };
        set({ widgets: [...widgets, newWidget] });
      },

      addWidgetAt: (module_key: string, x: number, y: number) => {
        const meta = MODULES_BY_KEY[module_key];
        if (!meta) {
          // eslint-disable-next-line no-console
          console.warn(`[dashboardStore] unknown module_key: ${module_key}`);
          return;
        }
        const widgets = get().widgets;
        const w = meta.default_w >= 8 ? meta.default_w : 6;
        // Clamp x so the widget doesn't spill off the right edge of the 12-
        // col grid. react-grid-layout's onDrop callback occasionally returns
        // values up to col+1 because the placeholder grew with the cursor.
        const safeX = Math.max(0, Math.min(12 - w, Math.floor(x)));
        const safeY = Math.max(0, Math.floor(y));
        const newWidget: DashboardWidget = {
          id: `${module_key}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          module_key,
          x: safeX,
          y: safeY,
          w,
          h: meta.default_h,
        };
        // Push the new widget in; RGL's collision handler will shuffle
        // overlapping neighbours down on the next layout pass.
        set({ widgets: [...widgets, newWidget] });
      },

      removeWidget: (id: string) =>
        set((s) => ({ widgets: s.widgets.filter((w) => w.id !== id) })),

      updateLayout: (next: DashboardWidget[]) => set({ widgets: next }),

      resetLayout: () => set({
        widgets: buildDefaultLayout(),
        // Don't touch `initialized` — we WANT this to act as a fresh re-seed
        // not as "wipe everything". Matches the "Reset to Default" button
        // semantics in the customize mode header.
        initialized: true,
      }),

      saveLayout: () => set((s) => ({
        savedWidgets: [...s.widgets],
        isCustomizing: false,
        draftSnapshot: null,
      })),

      cancelLayout: () => set((s) => ({
        widgets: s.draftSnapshot ?? s.widgets,
        isCustomizing: false,
        draftSnapshot: null,
      })),

      seedDefaultDashboard: () => {
        set((s) => {
          // Idempotent — never re-seed once initialized. If the user later
          // wipes everything they keep an empty dashboard until they re-add
          // widgets manually (or call resetLayout()).
          if (s.initialized) return s;
          return { widgets: buildDefaultLayout(), initialized: true };
        });
      },
    }),
    {
      name: "insightx_dashboard_layout",
      storage: createJSONStorage(() => localStorage),
      // Persist widgets + saved snapshot + the initialized flag. The
      // `isCustomizing` flag and `draftSnapshot` are session-only — a user
      // who reloads in the middle of an edit comes back out of customize mode.
      partialize: (state) => ({
        widgets: state.widgets,
        savedWidgets: state.savedWidgets,
        initialized: state.initialized,
      }),
    },
  ),
);
