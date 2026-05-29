import React from "react";
import { Info } from "lucide-react";

interface InsightCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  headerRight?: React.ReactNode;
  /** Optional small footer strip — used for legends, scales, action chips. */
  footer?: React.ReactNode;
}

export function InsightCard({ title, subtitle, children, className = "", headerRight, footer }: InsightCardProps) {
  return (
    <div className={`w-full h-full bg-white dark:bg-surface-card border border-gray-200 dark:border-white/5 rounded-xl shadow-sm flex flex-col overflow-hidden text-gray-900 dark:text-white ${className}`}>
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100 dark:border-white/5 flex items-start justify-between gap-4 flex-shrink-0 bg-transparent">
        <div className="min-w-0 flex-1">
          <h3 className="text-gray-900 dark:text-white text-base font-bold truncate tracking-tight">
            {title}
          </h3>
          {subtitle && (
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-1 font-medium">
              {subtitle}
            </p>
          )}
        </div>
        {(headerRight || subtitle) && (
          <div className="flex items-center gap-2 shrink-0">
            {headerRight}
            {!headerRight && subtitle && (
              <div className="text-slate-300 dark:text-slate-600" title={subtitle}>
                <Info className="w-4 h-4" />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 min-h-0 relative p-5 flex flex-col">
        {children}
      </div>

      {/* Optional footer — kept inside the card so it picks up the rounded
          corners and the dark/light surface treatment automatically. */}
      {footer && (
        <div className="px-5 py-3 border-t border-gray-100 dark:border-white/5 flex items-center justify-between gap-3 flex-shrink-0 bg-slate-50/60 dark:bg-white/[0.02]">
          {footer}
        </div>
      )}
    </div>
  );
}
