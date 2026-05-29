"use client";

/**
 * Placeholder for analytics modules that don't have a custom chart component
 * yet. Renders a friendly "coming soon" panel that still respects the grid
 * sizing so the user's layout doesn't break.
 *
 * As real chart components ship, we delete this fallback for the relevant
 * `module_key` by registering the real component in chartRegistry.ts.
 */

import { BarChart3 } from "lucide-react";

interface EmptyChartProps {
  moduleKey: string;
  chartType: string;
}

export function EmptyChart({ moduleKey, chartType }: EmptyChartProps) {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 p-4 text-center">
      <BarChart3 className="w-10 h-10 mb-2 opacity-40" />
      <p className="text-sm font-medium">Chart coming soon</p>
      <p className="text-xs opacity-70 mt-1">
        {moduleKey} · <span className="font-mono">{chartType}</span>
      </p>
    </div>
  );
}
