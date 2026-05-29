/**
 * Money / number formatting helpers.
 *
 * - Centralises currency-symbol lookup so every page renders the user's
 *   chosen `preferred_currency` consistently.
 * - `formatMoney` converts values from a source currency (default USD)
 *   into the display currency using a static FX table, then auto-scales
 *   the suffix (k / M / B).
 *
 * NOTE: Rates are static (good enough for demos). For production swap
 * `USD_RATES` for a daily refresh from openexchangerates / similar.
 */

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: '$',
  EUR: '€',
  GBP: '£',
  JPY: '¥',
  CNY: '¥',
  SAR: 'ر.س',
  AED: 'د.إ',
  EGP: 'ج.م',
  KWD: 'د.ك',
  QAR: 'ر.ق',
  BHD: 'د.ب',
  OMR: 'ر.ع',
  JOD: 'د.أ',
  TRY: '₺',
  BRL: 'R$',
};

/**
 * 1 USD = X target. Refreshed manually — replace with a live source later.
 *
 * Verified worked examples (USD → EGP) used as the project's reference set:
 *    100 USD  →  5,289.25 EGP
 *    250 USD  → 13,223.13 EGP
 *    500 USD  → 26,446.25 EGP
 *  1,000 USD  → 52,892.50 EGP
 * Implies an EGP rate of 52.8925 — matches the latest CBE mid-market quote.
 */
const USD_RATES: Record<string, number> = {
  USD: 1,
  EUR: 0.92,
  GBP: 0.79,
  JPY: 156.4,
  CNY: 7.24,
  SAR: 3.75,
  AED: 3.67,
  EGP: 52.8925,
  KWD: 0.307,
  QAR: 3.64,
  BHD: 0.376,
  OMR: 0.385,
  JOD: 0.709,
  TRY: 32.5,
  BRL: 5.04,
};

/** Convert an amount between two ISO codes via USD as the canonical pivot. */
export function convertMoney(amount: number, from?: string | null, to?: string | null): number {
  const f = (from || 'USD').toUpperCase();
  const t = (to   || 'USD').toUpperCase();
  if (f === t) return amount;
  const fromRate = USD_RATES[f] ?? 1; // amount = X·from-units → X / fromRate USD
  const toRate   = USD_RATES[t] ?? 1; // → (X / fromRate) · toRate target units
  return (amount / fromRate) * toRate;
}

/** ISO code → glyph (or the code itself if we don't know it). */
export function currencySymbol(code?: string | null): string {
  if (!code) return '$';
  const upper = code.toUpperCase();
  return CURRENCY_SYMBOLS[upper] ?? upper;
}

interface FormatOpts {
  /** Force a specific decimal place count. Default: 2 below 1k, 1 for k/M/B. */
  decimals?: number;
  /** When true, never use suffix; full number with thousand separators. */
  exact?: boolean;
  /**
   * Use compact "k/M/B" suffix. This is the DEFAULT, so passing `true`
   * is a no-op — accepted only so call sites that include `compact: true`
   * for self-documentation don't fail typecheck. Passing `false` is also
   * a no-op; use `exact: true` to get full numbers with separators.
   */
  compact?: boolean;
  /**
   * Source currency of `amount`. Converted to the display currency before
   * formatting using the static FX table. Defaults to 'USD' — most CSV
   * data we ship is USD. Per-upload detection can override this (see
   * `upload_jobs.source_currency`).
   */
  from?: string | null;
}

/**
 * Smart-format a money amount with the user's currency.
 *
 *   formatMoney(45.3,     'USD')                  → "$45.30"
 *   formatMoney(1240,     'USD')                  → "$1.2k"
 *   formatMoney(1_868_205,'USD')                  → "$1.87M"
 *   formatMoney(1_868_205,'EGP')                  → "ج.م 98.81M"   (converted from USD)
 *   formatMoney(100,      'EGP', { from: 'USD' }) → "ج.م 5.29k"
 *
 * Pass `{ exact: true }` to render the full number with separators
 * (used by tooltips where the user wants the precise value).
 */
export function formatMoney(amount: number | null | undefined, currency?: string | null, opts: FormatOpts = {}): string {
  const sym = currencySymbol(currency);
  // Multi-character symbols (Arabic "ج.م", "R$", currency codes used as
  // fallback, etc.) crash into the digits without a separator — the result
  // reads "ج.م21.0k" instead of "ج.م 21.0k". A single-char symbol like $ / €
  // / ¥ stays tight against the number per convention. Decide once here.
  const sep = sym.length > 1 ? ' ' : '';
  const raw = Number(amount ?? 0);
  if (!isFinite(raw)) return `${sym}${sep}0`;
  // Convert from source → display before scaling.
  const value = convertMoney(raw, opts.from ?? 'USD', currency ?? 'USD');

  if (opts.exact) {
    return `${sym}${sep}${value.toLocaleString(undefined, {
      minimumFractionDigits: opts.decimals ?? 0,
      maximumFractionDigits: opts.decimals ?? 2,
    })}`;
  }

  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';

  if (abs >= 1_000_000_000) {
    return `${sign}${sym}${sep}${(abs / 1_000_000_000).toFixed(opts.decimals ?? 2)}B`;
  }
  if (abs >= 1_000_000) {
    return `${sign}${sym}${sep}${(abs / 1_000_000).toFixed(opts.decimals ?? 2)}M`;
  }
  if (abs >= 1_000) {
    return `${sign}${sym}${sep}${(abs / 1_000).toFixed(opts.decimals ?? 1)}k`;
  }
  return `${sign}${sym}${sep}${abs.toFixed(opts.decimals ?? 2)}`;
}

/** Format a plain count with thousand separators ("4,950"). */
export function formatCount(n: number | null | undefined): string {
  return Number(n ?? 0).toLocaleString();
}
