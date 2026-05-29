import React from "react";
import { formatMoney } from "@/lib/format";

interface PayloadItem {
  value: number | string;
  name: string;
  color?: string;
  payload: any;
}

interface InsightTooltipProps {
  active?: boolean;
  payload?: PayloadItem[];
  label?: string;
  currency?: string;
  sourceCurrency?: string;
  valueFormatter?: (value: number | string) => string;
}

export function InsightTooltip({ active, payload, label, currency = "USD", sourceCurrency = "USD", valueFormatter }: InsightTooltipProps) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white/90 dark:bg-slate-800/90 backdrop-blur-md border border-gray-200 dark:border-white/10 p-3 rounded-lg shadow-xl !outline-none ring-1 ring-black/5 dark:ring-white/5">
        <p className="text-gray-900 dark:text-white font-bold text-sm mb-2">{label}</p>
        <div className="flex flex-col gap-1.5">
          {payload.map((p, i) => (
            <div key={i} className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full shadow-sm" style={{ backgroundColor: p.color || "#137fec" }} />
                <span className="text-slate-600 dark:text-slate-300 text-xs font-medium">{p.name}</span>
              </div>
              <span className="text-gray-900 dark:text-white text-sm font-bold">
                {valueFormatter 
                  ? valueFormatter(p.value) 
                  : (typeof p.value === 'number' && p.name.toLowerCase().includes('revenue') 
                      ? formatMoney(p.value, currency, { exact: true, decimals: 0, from: sourceCurrency }) 
                      : p.value.toLocaleString())}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return null;
}
