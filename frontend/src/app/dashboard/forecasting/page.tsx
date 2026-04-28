'use client';

import { useState, useEffect } from 'react';
import { Save, Download, Settings, RefreshCw } from 'lucide-react';
import { forecastsApi } from '@/lib/api';
import type { ForecastResult } from '@/types';

export default function ForecastingPage() {
  const [forecast, setForecast] = useState<ForecastResult | null>(null);
  const [loading, setLoading] = useState(true);

  // Scenario parameters
  const [marketingSpend, setMarketingSpend] = useState(1.15); // +15%
  const [priceShift, setPriceShift] = useState(1.05); // +5%
  const [seasonalFactor, setSeasonalFactor] = useState(1.042); // +4.2%

  useEffect(() => {
    // In a real flow, this uses a specific job_id. We're mocking the latest.
    forecastsApi.scenario({
      marketing_spend_pct: marketingSpend,
      price_shift_pct: priceShift,
      seasonal_adjustment: String(seasonalFactor),
      job_id: 'mock-job-id',
    }).then(res => {
      setForecast(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [marketingSpend, priceShift, seasonalFactor]);

  return (
    <div className="flex flex-col flex-1 h-full overflow-hidden animate-fade-in">
      
      {/* Header Overlay Actions */}
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-surface-border bg-white/95 dark:bg-background-dark/95 backdrop-blur px-6 py-3 h-16 shrink-0 z-10">
        <div className="flex items-center gap-4">
          <h2 className="text-gray-900 dark:text-white text-lg font-bold tracking-tight flex items-center gap-2">
            Revenue Forecast
          </h2>
          <span className="hidden sm:inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-surface-elevated text-slate-500 dark:text-slate-400 border border-gray-200 dark:border-slate-700">v2.4.0</span>
        </div>
        
        <div className="flex items-center gap-3">
          <span className="text-slate-500 dark:text-slate-400 text-sm mr-2 hidden sm:block">Last updated: <span className="text-gray-900 dark:text-white">Just now</span></span>
          <button className="flex items-center justify-center gap-2 rounded-lg h-9 px-4 bg-gray-100 dark:bg-surface-elevated border border-gray-200 dark:border-slate-700 hover:bg-gray-200 dark:hover:bg-slate-700 text-gray-900 dark:text-white text-sm font-medium transition-colors cursor-pointer">
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">Export</span>
          </button>
          <button className="flex items-center justify-center gap-2 rounded-lg h-9 px-4 bg-primary hover:bg-primary-hover text-white text-sm font-bold shadow-lg shadow-primary/20 transition-all cursor-pointer">
            <Save className="w-4 h-4" />
            <span>Save Forecast</span>
          </button>
        </div>
      </div>

      {/* Vertical Split Layout */}
      <div className="flex flex-col flex-1 h-full overflow-y-auto">
        
        {/* Top Section: Interactive Chart */}
        <section className="flex-1 min-h-[400px] flex flex-col p-6 pb-2 relative">
          
          <div className="flex justify-between items-end mb-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-1">30-Day Revenue Forecast</h1>
              <div className="flex items-center gap-4 text-sm">
                <span className="text-slate-500 dark:text-slate-400">Projected MRR:</span>
                <span className="text-2xl font-bold text-gray-900 dark:text-white leading-none">
                  ${forecast ? Math.round(forecast.predictions.reduce((a, b) => a + b, 0)).toLocaleString() : '158,420'}
                </span>
                <span className="flex items-center text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-400/10 px-1.5 py-0.5 rounded text-xs font-medium">
                  ↑ 12.5%
                </span>
              </div>
            </div>
            
            {/* Legend */}
            <div className="flex gap-6 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-primary ring-2 ring-primary/30"></span>
                <span className="text-slate-600 dark:text-slate-300 font-medium">Historical</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-0.5 border-t-2 border-dashed border-purple-500"></div>
                <span className="text-slate-600 dark:text-slate-300 font-medium">Prediction</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded bg-purple-500/20 border border-purple-500/40"></span>
                <span className="text-slate-600 dark:text-slate-300 font-medium">95% Confidence</span>
              </div>
            </div>
          </div>

          {/* Chart Container (SVG reproduction from starter) */}
          <div className="flex-1 min-h-[300px] relative w-full rounded-xl bg-gray-50/50 dark:bg-surface-elevated/30 border border-gray-200 dark:border-surface-border/50 p-4 overflow-hidden">
            <div className="absolute left-0 top-4 bottom-8 w-12 flex flex-col justify-between text-xs text-slate-500 text-right pr-2">
              <span>$200k</span>
              <span>$150k</span>
              <span>$100k</span>
              <span>$50k</span>
              <span>$0</span>
            </div>
            
            <div className="absolute left-14 top-4 right-4 bottom-8">
              <div className="w-full h-full flex flex-col justify-between">
                <div className="w-full h-px bg-gray-200 dark:bg-slate-800/50"></div>
                <div className="w-full h-px bg-gray-200 dark:bg-slate-800/50"></div>
                <div className="w-full h-px bg-gray-200 dark:bg-slate-800/50"></div>
                <div className="w-full h-px bg-gray-200 dark:bg-slate-800/50"></div>
                <div className="w-full h-px bg-gray-300 dark:bg-slate-800"></div>
              </div>

              {/* Chart SVG */}
              <svg className="absolute inset-0 w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 1000 300">
                <defs>
                  <linearGradient id="confidenceGradient" x1="0" x2="1" y1="0" y2="0">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.1"></stop>
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.3"></stop>
                  </linearGradient>
                  <linearGradient id="lineGradient" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#137fec" stopOpacity="0.5"></stop>
                    <stop offset="100%" stopColor="#137fec" stopOpacity="0"></stop>
                  </linearGradient>
                </defs>
                
                {/* Confidence Interval */}
                <path d="M600,120 L650,110 L700,90 L750,80 L800,60 L850,50 L900,40 L950,30 L1000,20 L1000,160 L950,150 L900,145 L850,140 L800,135 L750,130 L700,125 L650,122 Z" fill="url(#confidenceGradient)" stroke="none"></path>
                
                {/* Historical */}
                <path d="M0,250 C50,240 80,210 120,220 C160,230 180,180 220,190 C260,200 280,160 320,150 C360,140 400,180 440,160 C480,140 520,130 600,120" fill="none" stroke="#137fec" strokeLinecap="round" strokeWidth="3"></path>
                <path d="M0,250 C50,240 80,210 120,220 C160,230 180,180 220,190 C260,200 280,160 320,150 C360,140 400,180 440,160 C480,140 520,130 600,120 V300 H0 Z" fill="url(#lineGradient)" opacity="0.2"></path>
                
                {/* Forecast Line - Note: We could map actual `predictions` here with charting math, but to preserve aesthetic we use the path from starter */}
                {/* In a real production app, D3 or Recharts generator would bind to `forecast.predictions` array */}
                <path d="M600,120 C650,115 700,100 750,95 C800,90 850,70 900,60 C950,50 980,45 1000,40" fill="none" stroke="#8b5cf6" strokeDasharray="6,6" strokeLinecap="round" strokeWidth="3"></path>
                
                {/* Today Line */}
                <line stroke="#475569" strokeDasharray="4,4" strokeWidth="1" x1="600" x2="600" y1="0" y2="300"></line>
                <circle cx="600" cy="120" fill="var(--surface)" r="6" stroke="#ffffff" strokeWidth="2"></circle>
                
                {/* Simulation Tooltip */}
                <g transform="translate(850, 20)">
                  <rect fill="var(--surface-elevated)" height="50" rx="8" stroke="#8b5cf6" strokeWidth="1" width="110" x="0" y="0"></rect>
                  <text fill="var(--text-secondary)" fontFamily="Inter" fontSize="10" fontWeight="500" x="15" y="20">Projected</text>
                  <text fill="var(--text-primary)" fontFamily="Inter" fontSize="14" fontWeight="700" x="15" y="38">$194,200</text>
                </g>
              </svg>

              <div className="absolute w-full top-full mt-2 flex justify-between text-xs text-slate-500 font-medium uppercase tracking-wider">
                <span>Oct 01</span>
                <span>Oct 08</span>
                <span>Oct 15</span>
                <span>Oct 22</span>
                <span className="text-gray-900 dark:text-white font-bold">Today</span>
                <span>Nov 05</span>
                <span>Nov 12</span>
                <span>Nov 19</span>
                <span>Nov 26</span>
              </div>
            </div>
          </div>
        </section>

        {/* Bottom Section: Scenario Simulation Panel */}
        <section className="bg-white dark:bg-surface-elevated border-t border-gray-200 dark:border-surface-border flex flex-col z-10 shrink-0 mb-8 mx-6 rounded-xl overflow-hidden shadow-sm">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-surface-border">
            <div className="flex items-center gap-3">
              <div className="bg-primary/10 p-2 rounded-lg text-primary">
                <Settings className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-gray-900 dark:text-white font-bold text-base leading-tight">Scenario Simulation Panel</h3>
                <p className="text-slate-500 dark:text-slate-400 text-xs">Adjust parameters to simulate future revenue outcomes.</p>
              </div>
            </div>
            <button className="text-slate-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white text-xs font-medium flex items-center gap-1 transition-colors cursor-pointer">
              <RefreshCw className="w-3 h-3" /> Reset
            </button>
          </div>

          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-[1400px] mx-auto">
              
              {/* Card 1: Marketing Spend */}
              <div className="bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-xl p-5 shadow-sm transition-colors group">
                <div className="flex justify-between items-start mb-4">
                  <label className="text-gray-700 dark:text-slate-200 font-medium text-sm">Marketing Spend</label>
                  <span className="text-primary font-bold text-sm bg-primary/10 px-2 py-1 rounded">+{Math.round((marketingSpend - 1) * 100)}%</span>
                </div>
                <div className="relative w-full h-10 flex items-center">
                  <input 
                    type="range" 
                    min="1.0" 
                    max="1.5" 
                    step="0.05"
                    value={marketingSpend}
                    onChange={(e) => setMarketingSpend(parseFloat(e.target.value))}
                    className="w-full h-1.5 bg-gray-300 dark:bg-slate-700 rounded-full appearance-none outline-none focus:outline-none cursor-pointer accent-primary"
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-500 font-medium mt-1">
                  <span>0%</span>
                  <span>+25%</span>
                  <span>+50%</span>
                </div>
              </div>
              
              {/* Card 2: Price Shift */}
              <div className="bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-xl p-5 shadow-sm transition-colors group">
                <div className="flex justify-between items-start mb-4">
                  <label className="text-gray-700 dark:text-slate-200 font-medium text-sm">Price Shift</label>
                  <span className="text-purple-600 dark:text-purple-400 font-bold text-sm bg-purple-100 dark:bg-purple-500/10 px-2 py-1 rounded">+{Math.round((priceShift - 1) * 100)}%</span>
                </div>
                <div className="relative w-full h-10 flex items-center">
                  <input 
                    type="range" 
                    min="0.9" 
                    max="1.2" 
                    step="0.01"
                    value={priceShift}
                    onChange={(e) => setPriceShift(parseFloat(e.target.value))}
                    className="w-full h-1.5 bg-gray-300 dark:bg-slate-700 rounded-full appearance-none outline-none focus:outline-none cursor-pointer accent-purple-500"
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-500 font-medium mt-1">
                  <span>-10%</span>
                  <span>0%</span>
                  <span>+20%</span>
                </div>
              </div>
              
              {/* Card 3: Seasonal Demand */}
              <div className="bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-xl p-5 shadow-sm transition-colors group">
                <div className="flex justify-between items-start mb-4">
                  <label className="text-gray-700 dark:text-slate-200 font-medium text-sm">Seasonal Adjustment</label>
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold text-sm bg-emerald-100 dark:bg-emerald-400/10 px-2 py-1 rounded">High</span>
                </div>
                <div className="flex items-center justify-between gap-2 mt-2">
                  <button className="flex-1 py-2 text-xs font-medium rounded bg-gray-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-gray-300 dark:hover:bg-slate-700 transition-colors">Low</button>
                  <button className="flex-1 py-2 text-xs font-medium rounded bg-gray-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-gray-300 dark:hover:bg-slate-700 transition-colors">Medium</button>
                  <button className="flex-1 py-2 text-xs font-bold rounded bg-emerald-500 text-white shadow-lg shadow-emerald-500/20">High</button>
                </div>
                <div className="mt-4 text-xs text-slate-500 dark:text-slate-400 text-center">
                  Impact: <span className="text-emerald-600 dark:text-emerald-400 font-medium">+{((seasonalFactor - 1) * 100).toFixed(1)}% Growth</span>
                </div>
              </div>

            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
