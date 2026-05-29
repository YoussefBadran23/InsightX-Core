'use client';

import { useEffect, useMemo, useState } from 'react';
import { Save, Download, Settings, RefreshCw, Loader2, AlertCircle, Check } from 'lucide-react';
import { forecastsApi } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { useJobStore } from '@/stores/jobStore';
import { t } from '@/lib/i18n';
import { formatMoney } from '@/lib/format';
import type { Forecast } from '@/types';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { useChartTheme } from '@/components/charts/chartHelpers';

/**
 * Forecasting-page colour palette. Two of the four series take their colour
 * from the global theme tokens so light/dark mode flips them automatically;
 * the other two are domain-specific accents (violet = forecast, emerald =
 * scenario) that need to stay visually distinct from the brand blue.
 *
 * Defined as a small object instead of literal hex sprinkled across the JSX
 * so the chart can be re-themed by editing one place.
 */
function useForecastPalette() {
  const t = useChartTheme();
  return {
    historical: t.semantic.brand,        // theme-aware brand blue
    forecast:   '#8b5cf6',               // violet — forecast accent (domain)
    scenario:   t.semantic.positive,     // theme-aware emerald
    today:      t.text.muted,            // dashed "today" reference line
    grid:       t.gridStroke,
    tick:       t.text.muted,
    tooltipBg:  t.tooltip.background,
    tooltipBorder: t.tooltip.borderColor,
    tooltipText:   t.tooltip.color,
    surface:    t.surface,
    isDark:     t.isDark,
  };
}

type SeasonalLevel = 'low' | 'medium' | 'high';

/**
 * Trailing rolling mean. Returns null in any slot where the window had zero
 * non-null inputs (so leading days at the start of the forecast stay sane
 * instead of dragging the line toward zero). Used to flatten the daily zig-
 * zag in a 180-day Holt-Winters projection into a readable trend.
 */
function rollingMean(values: (number | null | undefined)[], window: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    const lo = Math.max(0, i - window + 1);
    let sum = 0;
    let count = 0;
    for (let j = lo; j <= i; j++) {
      const v = values[j];
      if (v != null && Number.isFinite(v)) {
        sum += v as number;
        count += 1;
      }
    }
    out.push(count > 0 ? sum / count : null);
  }
  return out;
}

const SMOOTH_WINDOW = 7; // 7-day rolling mean for the forecast / CI / scenario

export default function ForecastingPage() {
  const language = useUiStore((s) => s.language);
  const currency = useAuthStore((s) => s.user?.preferred_currency) || 'USD';
  const sourceCurrency = useJobStore((s) => s.sourceCurrency);
  const palette = useForecastPalette();
  const [base, setBase] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Scenario sliders. Both ranges are intentionally SYMMETRIC around 1.0 so
  // the visual "0%" tick lines up with the slider midpoint. Default values are
  // 1.0 (no change) — that way the chart loads showing the pure model output
  // and the user nudges from there.
  const [marketingMul, setMarketingMul] = useState(1.0);
  const [priceMul, setPriceMul] = useState(1.0);
  const [seasonal, setSeasonal] = useState<SeasonalLevel>('medium');

  const [adjusted, setAdjusted] = useState<Forecast['forecast'] | null>(null);
  const [adjLoading, setAdjLoading] = useState(false);
  // Visual feedback for the header buttons.
  const [exporting, setExporting] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Debounced scenario params — only sent to the API 350ms after the user
  // stops dragging a slider. Without this, every pixel of slider movement
  // fires a POST and the backend gets flooded with dozens of concurrent
  // requests, making each one slower (not faster).
  const [debouncedScenario, setDebouncedScenario] = useState({
    marketing: marketingMul,
    price:     priceMul,
    seasonal,
  });
  useEffect(() => {
    const id = setTimeout(() => {
      setDebouncedScenario({ marketing: marketingMul, price: priceMul, seasonal });
    }, 350);
    return () => clearTimeout(id);
  }, [marketingMul, priceMul, seasonal]);

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

  // ── Re-request scenario only on debounced params change (not every keystroke) ──
  useEffect(() => {
    if (!base) return;
    setAdjLoading(true);
    forecastsApi
      .scenario({
        marketing_spend_pct: debouncedScenario.marketing,
        price_shift_pct:     debouncedScenario.price,
        seasonal_adjustment: debouncedScenario.seasonal,
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
  }, [base, debouncedScenario]);

  // ── Build chart data: history first, then forecast (date-sorted) ──
  // Both halves get a 7-day trailing rolling mean. We used to leave historical
  // raw because "real revenue IS noisy", but on a 695-day series Recharts
  // renders as a wall of zigzag that buries the trend the user actually cares
  // about. Smoothing both sides yields a continuous, readable curve; the raw
  // numbers are still available in the CSV export for anyone who wants them.
  const chartData = useMemo(() => {
    if (!base) return [];
    const adjMap = new Map((adjusted || []).map((p) => [p.ds, p.yhat]));

    const histRaw = base.historical.map((p) => p.yhat as number | null);
    const smHist  = rollingMean(histRaw, SMOOTH_WINDOW);

    const fcRaw = base.forecast.map((p) => ({
      ds: p.ds,
      forecast: p.yhat as number | null,
      scenario: (adjMap.get(p.ds) ?? null) as number | null,
      lower: p.yhat_lower as number | null,
      upper: p.yhat_upper as number | null,
    }));
    const smForecast = rollingMean(fcRaw.map((r) => r.forecast), SMOOTH_WINDOW);
    const smScenario = rollingMean(fcRaw.map((r) => r.scenario), SMOOTH_WINDOW);
    const smLower    = rollingMean(fcRaw.map((r) => r.lower),    SMOOTH_WINDOW);
    const smUpper    = rollingMean(fcRaw.map((r) => r.upper),    SMOOTH_WINDOW);

    const rows: any[] = [];
    for (let i = 0; i < base.historical.length; i++) {
      rows.push({ ds: base.historical[i].ds, actual: smHist[i] });
    }
    for (let i = 0; i < fcRaw.length; i++) {
      const lo = smLower[i];
      const up = smUpper[i];
      rows.push({
        ds:        fcRaw[i].ds,
        forecast:  smForecast[i],
        scenario:  smScenario[i],
        ci_band:   (lo != null && up != null) ? [lo, up] : null,
      });
    }
    return rows;
  }, [base, adjusted]);

  const lastHistorical = base?.historical?.[base.historical.length - 1]?.ds;

  const projectedMrr = useMemo(() => {
    const arr = adjusted ?? base?.forecast ?? [];
    return arr.reduce((s: number, p: any) => s + (p.yhat || 0), 0);
  }, [adjusted, base]);

  // ── Stakeholder-friendly insights ────────────────────────────────────────
  // Surface the most useful numbers as cards so a non-technical viewer doesn't
  // have to read the chart to understand the forecast. Each value lives in
  // source currency (BRL/USD/etc.) — `formatMoney` converts to the display
  // currency at render time.
  const insights = useMemo(() => {
    if (!base) return null;
    const hist = base.historical;
    const fc = adjusted ?? base.forecast;
    if (hist.length === 0 || fc.length === 0) return null;
    const last30 = hist.slice(-30);
    const next30 = fc.slice(0, 30);
    const last30Avg = last30.reduce((s, p) => s + (p.yhat || 0), 0) / Math.max(1, last30.length);
    const next30Avg = next30.reduce((s, p: any) => s + (p.yhat || 0), 0) / Math.max(1, next30.length);
    const totalNext = fc.reduce((s, p: any) => s + (p.yhat || 0), 0);
    const deltaPct = last30Avg !== 0 ? ((next30Avg - last30Avg) / last30Avg) * 100 : 0;
    return { last30Avg, next30Avg, totalNext, deltaPct, horizon: fc.length };
  }, [base, adjusted]);

  // ── Header actions ──────────────────────────────────────────────────────
  // Export: dump every chart row to a CSV the user can hand to Excel / a
  // stakeholder. Save: snapshot the same payload + the user's scenario
  // settings as JSON so they can re-load it later or send it for review.
  // Both are pure client-side actions — no backend round-trip needed.
  const escapeCsv = (val: unknown): string => {
    if (val === null || val === undefined) return '';
    const s = String(val);
    return `"${s.replace(/"/g, '""')}"`;
  };

  const handleExport = () => {
    if (!base || chartData.length === 0 || exporting) return;
    setExporting(true);
    try {
      const header = ['date', 'historical', 'forecast', 'scenario', 'ci_lower', 'ci_upper'];
      const rows = chartData.map((r: any) => {
        const ci = r.ci_band as [number, number] | null | undefined;
        return [
          r.ds,
          r.actual ?? '',
          r.forecast ?? '',
          r.scenario ?? '',
          ci ? ci[0] : '',
          ci ? ci[1] : '',
        ];
      });
      const csv = [header, ...rows].map((row) => row.map(escapeCsv).join(',')).join('\r\n');
      const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const stamp = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `insightx_forecast_${stamp}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const handleSave = () => {
    if (!base) return;
    const snapshot = {
      saved_at: new Date().toISOString(),
      method: base.method,
      forecast_periods: base.forecast_periods,
      scenario: {
        marketing_spend_pct: marketingMul,
        price_shift_pct: priceMul,
        seasonal_adjustment: seasonal,
      },
      projected_revenue: projectedMrr,
      historical: base.historical,
      forecast: base.forecast,
      adjusted_forecast: adjusted ?? null,
    };
    const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    a.href = url;
    a.download = `insightx_forecast_${stamp}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    // Also persist the scenario in localStorage so it auto-restores on next
    // visit — gives "Save Forecast" a non-file side-effect too.
    try {
      localStorage.setItem('insightx_saved_forecast_scenario', JSON.stringify(snapshot.scenario));
    } catch { /* quota / private-mode — ignore */ }
    setSavedAt(Date.now());
    setTimeout(() => setSavedAt(null), 2200);
  };

  // Restore last saved scenario on mount.
  useEffect(() => {
    try {
      const raw = localStorage.getItem('insightx_saved_forecast_scenario');
      if (!raw) return;
      const s = JSON.parse(raw);
      if (typeof s?.marketing_spend_pct === 'number') setMarketingMul(s.marketing_spend_pct);
      if (typeof s?.price_shift_pct === 'number') setPriceMul(s.price_shift_pct);
      if (s?.seasonal_adjustment === 'low' || s?.seasonal_adjustment === 'medium' || s?.seasonal_adjustment === 'high') {
        setSeasonal(s.seasonal_adjustment);
      }
    } catch { /* corrupt entry — ignore */ }
  }, []);

  return (
    <div className="flex flex-col flex-1 h-full overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-white/10 bg-white/95 dark:bg-surface-card/95 backdrop-blur px-6 py-3 h-16 shrink-0 z-10">
        <div className="flex items-center gap-4">
          <h2 className="text-gray-900 dark:text-white text-lg font-bold tracking-tight flex items-center gap-2">
            {t('fc_title', language)}
          </h2>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-slate-500 dark:text-slate-400 text-sm me-2 hidden sm:block">
            {base ? `${base.forecast_periods}-${t('fc_dayForecast', language)}` : t('fc_loading', language)}
          </span>
          <button
            onClick={handleExport}
            disabled={!base || exporting || chartData.length === 0}
            className="flex items-center justify-center gap-2 rounded-lg h-9 px-4 bg-gray-100 dark:bg-black/40 border border-slate-200 dark:border-white/10 hover:bg-gray-200 dark:hover:bg-black/60 text-gray-900 dark:text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {exporting
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Download className="w-4 h-4" />}
            <span className="hidden sm:inline">{t('fc_export', language)}</span>
          </button>
          <button
            onClick={handleSave}
            disabled={!base}
            className="flex items-center justify-center gap-2 rounded-lg h-9 px-4 bg-primary hover:bg-primary-hover text-white text-sm font-bold shadow-lg shadow-primary/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
          >
            {savedAt
              ? <Check className="w-4 h-4" />
              : <Save className="w-4 h-4" />}
            <span>{savedAt ? t('fc_saved', language) : t('fc_save', language)}</span>
          </button>
        </div>
      </div>

      <div className="flex flex-col flex-1 h-full overflow-y-auto">
        {/* Quick Stats Panel — premium glassmorphic KPI strip. Each card uses
            a translucent surface + backdrop-blur + inset white-ring so it
            reads as "frosted glass" on both light and dark backgrounds. The
            DELTA card switches accent based on direction (positive emerald,
            negative amber); the TOTAL card carries the forecast violet to
            tie it visually to the dashed forecast line below. */}
        {insights && (
          <section className="px-6 pt-6">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {/* — Last 30 actual — */}
              <div
                className="relative rounded-xl p-4 overflow-hidden transition-all hover:-translate-y-0.5 backdrop-blur-sm"
                style={{
                  background: palette.isDark
                    ? 'linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01))'
                    : 'linear-gradient(135deg, rgba(255,255,255,0.92), rgba(248,250,252,0.85))',
                  border: `1px solid ${palette.tooltipBorder}`,
                  boxShadow: palette.isDark
                    ? '0 1px 0 rgba(255,255,255,0.05) inset, 0 4px 16px rgba(0,0,0,0.25)'
                    : '0 1px 0 rgba(255,255,255,0.9) inset, 0 4px 12px rgba(15,23,42,0.06)',
                }}
              >
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 font-bold">{t('fc_statLast30', language)}</p>
                <p className="text-xl font-bold text-slate-900 dark:text-white mt-1 tracking-tight">
                  {formatMoney(insights.last30Avg, currency, { exact: true, decimals: 0, from: sourceCurrency })}
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{t('fc_statPerDay', language)}</p>
              </div>

              {/* — Next 30 projected — */}
              <div
                className="relative rounded-xl p-4 overflow-hidden transition-all hover:-translate-y-0.5 backdrop-blur-sm"
                style={{
                  background: palette.isDark
                    ? `linear-gradient(135deg, ${palette.historical}1a, rgba(255,255,255,0.01))`
                    : `linear-gradient(135deg, ${palette.historical}0a, rgba(255,255,255,0.92))`,
                  border: `1px solid ${palette.historical}33`,
                  boxShadow: palette.isDark
                    ? `0 1px 0 rgba(255,255,255,0.05) inset, 0 4px 16px ${palette.historical}22`
                    : `0 1px 0 rgba(255,255,255,0.9) inset, 0 4px 12px ${palette.historical}1a`,
                }}
              >
                <p className="text-xs uppercase tracking-wide font-bold" style={{ color: palette.historical }}>
                  {t('fc_statNext30', language)}
                </p>
                <p className="text-xl font-bold text-slate-900 dark:text-white mt-1 tracking-tight">
                  {formatMoney(insights.next30Avg, currency, { exact: true, decimals: 0, from: sourceCurrency })}
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{t('fc_statPerDay', language)}</p>
              </div>

              {/* — Delta vs prior — */}
              <div
                className="relative rounded-xl p-4 overflow-hidden transition-all hover:-translate-y-0.5 backdrop-blur-sm"
                style={{
                  background: palette.isDark
                    ? insights.deltaPct >= 0
                      ? 'linear-gradient(135deg, rgba(16,185,129,0.18), rgba(255,255,255,0.01))'
                      : 'linear-gradient(135deg, rgba(245,158,11,0.18), rgba(255,255,255,0.01))'
                    : insights.deltaPct >= 0
                      ? 'linear-gradient(135deg, rgba(16,185,129,0.10), rgba(255,255,255,0.92))'
                      : 'linear-gradient(135deg, rgba(245,158,11,0.10), rgba(255,255,255,0.92))',
                  border: insights.deltaPct >= 0
                    ? '1px solid rgba(16,185,129,0.35)'
                    : '1px solid rgba(245,158,11,0.35)',
                  boxShadow: palette.isDark
                    ? insights.deltaPct >= 0
                      ? '0 1px 0 rgba(255,255,255,0.05) inset, 0 4px 16px rgba(16,185,129,0.20)'
                      : '0 1px 0 rgba(255,255,255,0.05) inset, 0 4px 16px rgba(245,158,11,0.20)'
                    : '0 1px 0 rgba(255,255,255,0.9) inset, 0 4px 12px rgba(15,23,42,0.05)',
                }}
              >
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 font-bold">{t('fc_statChange', language)}</p>
                <p className={`text-xl font-bold mt-1 tracking-tight ${
                  insights.deltaPct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'
                }`}>
                  {insights.deltaPct >= 0 ? '+' : ''}{insights.deltaPct.toFixed(1)}%
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{t('fc_statChangeSub', language)}</p>
              </div>

              {/* — Total projected (horizon) — uses forecast violet to tie
                  visually to the dashed forecast line on the chart below. */}
              <div
                className="relative rounded-xl p-4 overflow-hidden transition-all hover:-translate-y-0.5 backdrop-blur-sm"
                style={{
                  background: palette.isDark
                    ? `linear-gradient(135deg, ${palette.forecast}22, rgba(255,255,255,0.01))`
                    : `linear-gradient(135deg, ${palette.forecast}12, rgba(255,255,255,0.92))`,
                  border: `1px solid ${palette.forecast}40`,
                  boxShadow: palette.isDark
                    ? `0 1px 0 rgba(255,255,255,0.05) inset, 0 4px 16px ${palette.forecast}33`
                    : `0 1px 0 rgba(255,255,255,0.9) inset, 0 4px 12px ${palette.forecast}1f`,
                }}
              >
                <p className="text-xs uppercase tracking-wide font-bold" style={{ color: palette.forecast }}>
                  {t('fc_statTotal', language)}
                </p>
                <p className="text-xl font-bold mt-1 tracking-tight" style={{ color: palette.forecast }}>
                  {formatMoney(insights.totalNext, currency, { exact: true, decimals: 0, from: sourceCurrency })}
                </p>
                <p className="text-[11px] mt-0.5" style={{ color: `${palette.forecast}b3` }}>
                  {insights.horizon}-{t('fc_statTotalSub', language)}
                </p>
              </div>
            </div>
          </section>
        )}

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
                  {formatMoney(projectedMrr, currency, { exact: true, decimals: 0, from: sourceCurrency })}
                </span>
                {adjLoading && <Loader2 className="w-4 h-4 text-primary animate-spin" />}
              </div>
            </div>

            <div className="flex gap-6 text-sm">
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-0.5 rounded-full"
                  style={{ background: palette.historical }}
                />
                <span className="text-slate-600 dark:text-slate-300 font-medium">{t('fc_legendHistorical', language)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-0.5 border-t-2 border-dashed"
                  style={{ borderColor: palette.forecast }}
                />
                <span className="text-slate-600 dark:text-slate-300 font-medium">{t('fc_legendForecast', language)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-3 rounded"
                  style={{
                    background: `${palette.forecast}1a`,
                    border: `1px solid ${palette.forecast}33`,
                  }}
                />
                <span className="text-slate-600 dark:text-slate-300 font-medium">{t('fc_legendCI', language)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-0.5 border-t-2 border-dashed"
                  style={{ borderColor: palette.scenario }}
                />
                <span className="text-slate-600 dark:text-slate-300 font-medium">{t('fc_legendScenario', language)}</span>
              </div>
            </div>
          </div>

          <div className="flex-1 min-h-[300px] relative w-full rounded-xl bg-slate-50/50 dark:bg-black/30 border border-slate-200 dark:border-white/10 p-4 overflow-hidden shadow-sm">
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
                <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 30, left: 8 }}>
                  <defs>
                    {/* Historical fade — brand-tinted vertical fade, theme-aware. */}
                    <linearGradient id="histFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"   stopColor={palette.historical} stopOpacity={palette.isDark ? 0.28 : 0.20} />
                      <stop offset="100%" stopColor={palette.historical} stopOpacity={0} />
                    </linearGradient>
                    {/* CI band — vertical sandwich gradient. Strongest in the
                        middle of the band so the "cloud of uncertainty" reads
                        as a soft cloud, not a stamped block. */}
                    <linearGradient id="ciFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"   stopColor={palette.forecast} stopOpacity={0.06} />
                      <stop offset="50%"  stopColor={palette.forecast} stopOpacity={0.16} />
                      <stop offset="100%" stopColor={palette.forecast} stopOpacity={0.06} />
                    </linearGradient>
                    {/* Premium glow — wraps the forecast + scenario lines so
                        they "float" off the canvas. stdDeviation is bumped in
                        dark mode (more diffusion) since dark backgrounds make
                        glow feel weaker. */}
                    <filter id="forecasting-glow" x="-20%" y="-50%" width="140%" height="200%">
                      <feGaussianBlur stdDeviation={palette.isDark ? 4 : 2.5} result="blur" />
                      <feComposite in="SourceGraphic" in2="blur" operator="over" />
                    </filter>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke={palette.grid}
                    strokeOpacity={0.7}
                  />
                  <XAxis
                    dataKey="ds"
                    tick={{ fontSize: 11, fill: palette.tick }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={40}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: palette.tick }}
                    tickLine={false}
                    axisLine={false}
                    width={72}
                    tickMargin={8}
                    // Clamp to zero. Early historical days in some seeds have
                    // negative net revenue (refunds > sales) and the CI lower
                    // bound dips negative on the first few forecast days —
                    // visually that just reads "revenue can go below zero",
                    // which is confusing. The CSV export still has the raw
                    // numbers for anyone who wants the unclamped data.
                    domain={[0, 'auto']}
                    allowDataOverflow={false}
                    tickFormatter={(v) => formatMoney(v, currency, { from: sourceCurrency })}
                  />
                  <Tooltip
                    formatter={(v: any) =>
                      typeof v === 'number'
                        ? formatMoney(v, currency, { exact: true, decimals: 0, from: sourceCurrency })
                        : v
                    }
                    contentStyle={{
                      borderRadius: 10,
                      border: `1px solid ${palette.tooltipBorder}`,
                      background: palette.tooltipBg,
                      color: palette.tooltipText,
                      boxShadow: palette.isDark
                        ? '0 8px 24px rgba(0,0,0,0.45)'
                        : '0 4px 12px rgba(15, 23, 42, 0.10)',
                    }}
                    labelStyle={{ color: palette.tick, fontSize: 11, fontWeight: 600 }}
                  />
                  {/* CI band first — sits behind the lines as a soft cloud. */}
                  <Area
                    type="monotone"
                    dataKey="ci_band"
                    stroke="none"
                    fill="url(#ciFill)"
                    name="80% Confidence"
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                  {/* Historical actual — brand blue, smoothed, gentle fill. */}
                  <Area
                    type="monotone"
                    dataKey="actual"
                    stroke={palette.historical}
                    strokeWidth={2.25}
                    fill="url(#histFill)"
                    name="Historical"
                    connectNulls={false}
                  />
                  {/* Forecast — violet, dashed + animated marching-ants flow
                      so the eye reads it as movement into the future. The
                      `forecasting-glow` filter wraps the stroke with a soft
                      halo so the line "floats" off the canvas. */}
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    stroke={palette.forecast}
                    strokeWidth={2.5}
                    strokeDasharray="6 6"
                    dot={false}
                    name="Forecast"
                    connectNulls={false}
                    isAnimationActive={false}
                    className="animate-dash-flow"
                    filter="url(#forecasting-glow)"
                  />
                  {/* Scenario overlay — emerald, finer dash so it sits as a
                      "what-if" beside the baseline forecast. Same glow. */}
                  <Line
                    type="monotone"
                    dataKey="scenario"
                    stroke={palette.scenario}
                    strokeWidth={2.25}
                    strokeDasharray="2 4"
                    dot={false}
                    name="Scenario"
                    connectNulls={false}
                    isAnimationActive={false}
                    className="animate-dash-flow"
                    filter="url(#forecasting-glow)"
                  />
                  {lastHistorical && (
                    <ReferenceLine
                      x={lastHistorical}
                      stroke={palette.today}
                      strokeOpacity={0.6}
                      strokeDasharray="4 4"
                      label={{
                        value: t('fc_today', language),
                        position: 'insideTopRight',
                        fill: palette.tick,
                        fontSize: 11,
                      }}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        {/* Scenario sliders */}
        <section className="bg-white dark:bg-surface-card border-t border-slate-200 dark:border-white/10 flex flex-col z-10 shrink-0 mb-8 mx-6 rounded-xl overflow-hidden shadow-sm">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-white/10">
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
              <div className="bg-slate-50 dark:bg-black/30 border border-slate-200 dark:border-white/10 rounded-xl p-5 shadow-sm">
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

              <div className="bg-slate-50 dark:bg-black/30 border border-slate-200 dark:border-white/10 rounded-xl p-5 shadow-sm">
                <div className="flex justify-between items-start mb-4">
                  <label className="text-gray-700 dark:text-slate-200 font-medium text-sm">{t('fc_priceShift', language)}</label>
                  <span className="text-purple-600 dark:text-purple-400 font-bold text-sm bg-purple-100 dark:bg-purple-500/10 px-2 py-1 rounded">
                    {priceMul >= 1 ? '+' : ''}
                    {Math.round((priceMul - 1) * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  // Symmetric range so value=1.0 (the "0%" tick) sits exactly
                  // at the slider midpoint — see the marketing slider above
                  // for the same pattern.
                  min="0.7"
                  max="1.3"
                  step="0.01"
                  value={priceMul}
                  onChange={(e) => setPriceMul(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-gray-300 dark:bg-slate-700 rounded-full appearance-none outline-none cursor-pointer accent-purple-500"
                />
                <div className="flex justify-between text-xs text-slate-500 font-medium mt-1">
                  <span>-30%</span>
                  <span>0%</span>
                  <span>+30%</span>
                </div>
              </div>

              <div className="bg-slate-50 dark:bg-black/30 border border-slate-200 dark:border-white/10 rounded-xl p-5 shadow-sm">
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
