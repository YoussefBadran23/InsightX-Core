'use client';

import { useEffect, useMemo, useState } from 'react';
import { Save, Download, Settings, RefreshCw, Loader2, AlertCircle } from 'lucide-react';
import { forecastsApi } from '@/lib/api';
import { useUiStore } from '@/stores/uiStore';
import { t } from '@/lib/i18n';
import type { Forecast } from '@/types';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

type SeasonalLevel = 'low' | 'medium' | 'high';

export default function ForecastingPage() {
  const language = useUiStore((s) => s.language);
  const [base, setBase] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Scenario sliders
  const [marketingMul, setMarketingMul] = useState(1.15); // +15%
  const [priceMul, setPriceMul] = useState(1.05);          // +5%
  const [seasonal, setSeasonal] = useState<SeasonalLevel>('high');

  const [adjusted, setAdjusted] = useState<Forecast['forecast'] | null>(null);
  const [adjLoading, setAdjLoading] = useState(false);

  // ── Load base forecast on mount ──
  useEffect(() => {
    setLoading(true);
    forecastsApi
      .latest()
      .then((res) => {
        setBase(res.data as Forecast);
        setError(null);
      })
      .catch((e) => {
        setError(e?.response?.data?.detail || t('fc_noForecast', language));
      })
      .finally(() => setLoading(false));
  }, []);

  // ── Re-request scenario whenever a slider moves ──
  useEffect(() => {
    if (!base) return;
    setAdjLoading(true);
    forecastsApi
      .scenario({
        marketing_spend_pct: marketingMul,
        price_shift_pct: priceMul,
        seasonal_adjustment: seasonal,
      })
      .then((res) => {
        setAdjusted(
          (res.data?.forecast || []).map((p: any) => ({
            ds: p.ds,
            yhat: p.yhat,
            yhat_lower: p.yhat_lower,
            yhat_upper: p.yhat_upper,
            is_historical: false,
          })),
        );
      })
      .catch(() => setAdjusted(null))
      .finally(() => setAdjLoading(false));
  }, [base, marketingMul, priceMul, seasonal]);

  // ── Build chart data: history first, then forecast (date-sorted) ──
  const chartData = useMemo(() => {
    if (!base) return [];
    const adjMap = new Map((adjusted || []).map((p) => [p.ds, p.yhat]));
    const rows: any[] = [];
    for (const p of base.historical) {
      rows.push({ ds: p.ds, actual: p.yhat });
    }
    for (const p of base.forecast) {
      rows.push({
        ds: p.ds,
        forecast: p.yhat,
        scenario: adjMap.get(p.ds) ?? null,
        lower: p.yhat_lower,
        upper: p.yhat_upper,
        ci_band: [p.yhat_lower, p.yhat_upper],
      });
    }
    return rows;
  }, [base, adjusted]);

  const lastHistorical = base?.historical?.[base.historical.length - 1]?.ds;

  const projectedMrr = useMemo(() => {
    const arr = adjusted ?? base?.forecast ?? [];
    return arr.reduce((s: number, p: any) => s + (p.yhat || 0), 0);
  }, [adjusted, base]);

  return (
    <div className="flex flex-col flex-1 h-full overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-surface-border bg-white/95 dark:bg-background-dark/95 backdrop-blur px-6 py-3 h-16 shrink-0 z-10">
        <div className="flex items-center gap-4">
          <h2 className="text-gray-900 dark:text-white text-lg font-bold tracking-tight flex items-center gap-2">
            {t('fc_title', language)}
          </h2>
          {base && (
            <span className="hidden sm:inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-surface-elevated text-slate-500 dark:text-slate-400 border border-gray-200 dark:border-slate-700">
              {base.method}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-slate-500 dark:text-slate-400 text-sm me-2 hidden sm:block">
            {base ? `${base.forecast_periods}-${t('fc_dayForecast', language)}` : t('fc_loading', language)}
          </span>
          <button className="flex items-center justify-center gap-2 rounded-lg h-9 px-4 bg-gray-100 dark:bg-surface-elevated border border-gray-200 dark:border-slate-700 hover:bg-gray-200 dark:hover:bg-slate-700 text-gray-900 dark:text-white text-sm font-medium transition-colors cursor-pointer">
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">{t('fc_export', language)}</span>
          </button>
          <button className="flex items-center justify-center gap-2 rounded-lg h-9 px-4 bg-primary hover:bg-primary-hover text-white text-sm font-bold shadow-lg shadow-primary/20 transition-all cursor-pointer">
            <Save className="w-4 h-4" />
            <span>{t('fc_save', language)}</span>
          </button>
        </div>
      </div>

      <div className="flex flex-col flex-1 h-full overflow-y-auto">
        {/* Chart */}
        <section className="flex-1 min-h-[400px] flex flex-col p-6 pb-2 relative">
          <div className="flex justify-between items-end mb-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-1">
                {base ? `${base.forecast_periods}-${t('fc_chartTitle', language)}` : t('fc_title', language)}
              </h1>
              <div className="flex items-center gap-4 text-sm">
                <span className="text-slate-500 dark:text-slate-400">{t('fc_projected', language)}</span>
                <span className="text-2xl font-bold text-gray-900 dark:text-white leading-none">
                  ${Math.round(projectedMrr).toLocaleString()}
                </span>
                {adjLoading && <Loader2 className="w-4 h-4 text-primary animate-spin" />}
              </div>
            </div>

            <div className="flex gap-6 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-primary"></span>
                <span className="text-slate-600 dark:text-slate-300 font-medium">{t('fc_legendHistorical', language)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-0.5 bg-purple-500"></span>
                <span className="text-slate-600 dark:text-slate-300 font-medium">{t('fc_legendForecast', language)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded bg-purple-500/20 border border-purple-500/40"></span>
                <span className="text-slate-600 dark:text-slate-300 font-medium">{t('fc_legendCI', language)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-0.5 border-t-2 border-dashed border-emerald-500"></span>
                <span className="text-slate-600 dark:text-slate-300 font-medium">{t('fc_legendScenario', language)}</span>
              </div>
            </div>
          </div>

          <div className="flex-1 min-h-[300px] relative w-full rounded-xl bg-gray-50/50 dark:bg-surface-elevated/30 border border-gray-200 dark:border-surface-border/50 p-4 overflow-hidden">
            {loading ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-primary animate-spin" />
              </div>
            ) : error ? (
              <div className="absolute inset-0 flex items-center justify-center text-center px-6">
                <div>
                  <AlertCircle className="w-10 h-10 text-amber-500 mx-auto mb-3" />
                  <p className="text-slate-600 dark:text-slate-300 max-w-md">{error}</p>
                </div>
              </div>
            ) : chartData.length === 0 ? (
              <div className="absolute inset-0 flex items-center justify-center text-slate-500">
                {t('fc_emptyChart', language)}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 30, left: 0 }}>
                  <defs>
                    <linearGradient id="histFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#137fec" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#137fec" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                  <XAxis
                    dataKey="ds"
                    tick={{ fontSize: 11 }}
                    opacity={0.6}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={40}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    opacity={0.6}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `$${Math.round(v / 1000)}k`}
                  />
                  <Tooltip
                    formatter={(v: any) =>
                      typeof v === 'number' ? `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : v
                    }
                    contentStyle={{
                      borderRadius: 8,
                      border: '1px solid rgba(0,0,0,0.1)',
                      background: 'var(--surface, white)',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {/* CI band */}
                  <Area
                    type="monotone"
                    dataKey="ci_band"
                    stroke="none"
                    fill="#8b5cf6"
                    fillOpacity={0.18}
                    name="80% Confidence"
                  />
                  {/* Historical actual */}
                  <Area
                    type="monotone"
                    dataKey="actual"
                    stroke="#137fec"
                    strokeWidth={2}
                    fill="url(#histFill)"
                    name="Historical"
                    connectNulls={false}
                  />
                  {/* Forecast baseline */}
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    stroke="#8b5cf6"
                    strokeWidth={3}
                    dot={false}
                    name="Forecast"
                    connectNulls={false}
                  />
                  {/* Scenario overlay */}
                  <Line
                    type="monotone"
                    dataKey="scenario"
                    stroke="#10b981"
                    strokeWidth={2.5}
                    strokeDasharray="6 6"
                    dot={false}
                    name="Scenario"
                    connectNulls={false}
                  />
                  {lastHistorical && (
                    <ReferenceLine x={lastHistorical} stroke="#94a3b8" strokeDasharray="4 4" />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        {/* Scenario sliders */}
        <section className="bg-white dark:bg-surface-elevated border-t border-gray-200 dark:border-surface-border flex flex-col z-10 shrink-0 mb-8 mx-6 rounded-xl overflow-hidden shadow-sm">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-surface-border">
            <div className="flex items-center gap-3">
              <div className="bg-primary/10 p-2 rounded-lg text-primary">
                <Settings className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-gray-900 dark:text-white font-bold text-base leading-tight">{t('fc_scenarioTitle', language)}</h3>
                <p className="text-slate-500 dark:text-slate-400 text-xs">{t('fc_scenarioDesc', language)}</p>
              </div>
            </div>
            <button
              onClick={() => {
                setMarketingMul(1.0);
                setPriceMul(1.0);
                setSeasonal('medium');
              }}
              className="text-slate-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white text-xs font-medium flex items-center gap-1 transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" /> {t('fc_reset', language)}
            </button>
          </div>

          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-[1400px] mx-auto">
              <div className="bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-xl p-5 shadow-sm">
                <div className="flex justify-between items-start mb-4">
                  <label className="text-gray-700 dark:text-slate-200 font-medium text-sm">{t('fc_marketing', language)}</label>
                  <span className="text-primary font-bold text-sm bg-primary/10 px-2 py-1 rounded">
                    {marketingMul >= 1 ? '+' : ''}
                    {Math.round((marketingMul - 1) * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.5"
                  step="0.05"
                  value={marketingMul}
                  onChange={(e) => setMarketingMul(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-gray-300 dark:bg-slate-700 rounded-full appearance-none outline-none cursor-pointer accent-primary"
                />
                <div className="flex justify-between text-xs text-slate-500 font-medium mt-1">
                  <span>-50%</span>
                  <span>0%</span>
                  <span>+50%</span>
                </div>
              </div>

              <div className="bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-xl p-5 shadow-sm">
                <div className="flex justify-between items-start mb-4">
                  <label className="text-gray-700 dark:text-slate-200 font-medium text-sm">{t('fc_priceShift', language)}</label>
                  <span className="text-purple-600 dark:text-purple-400 font-bold text-sm bg-purple-100 dark:bg-purple-500/10 px-2 py-1 rounded">
                    {priceMul >= 1 ? '+' : ''}
                    {Math.round((priceMul - 1) * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0.8"
                  max="1.3"
                  step="0.01"
                  value={priceMul}
                  onChange={(e) => setPriceMul(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-gray-300 dark:bg-slate-700 rounded-full appearance-none outline-none cursor-pointer accent-purple-500"
                />
                <div className="flex justify-between text-xs text-slate-500 font-medium mt-1">
                  <span>-20%</span>
                  <span>0%</span>
                  <span>+30%</span>
                </div>
              </div>

              <div className="bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-surface-border rounded-xl p-5 shadow-sm">
                <div className="flex justify-between items-start mb-4">
                  <label className="text-gray-700 dark:text-slate-200 font-medium text-sm">{t('fc_seasonal', language)}</label>
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold text-sm bg-emerald-100 dark:bg-emerald-400/10 px-2 py-1 rounded uppercase">
                    {t(`fc_${seasonal}` as any, language)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2 mt-2">
                  {(['low', 'medium', 'high'] as const).map((l) => (
                    <button
                      key={l}
                      onClick={() => setSeasonal(l)}
                      className={`flex-1 py-2 text-xs font-medium rounded transition-colors ${
                        seasonal === l
                          ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20 font-bold'
                          : 'bg-gray-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-gray-300 dark:hover:bg-slate-700'
                      }`}
                    >
                      {t(`fc_${l}` as any, language)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
