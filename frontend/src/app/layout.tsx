import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { cookies } from "next/headers";

// ── Anti-FOUC theme script ─────────────────────────────────────────────────
// Runs synchronously before React hydrates, so the correct class is on <html>
// before the first paint — no flash of wrong theme.
const THEME_SCRIPT = `
(function () {
  try {
    var raw   = localStorage.getItem('insightx-ui');
    var state = raw ? JSON.parse(raw) : {};
    var theme = (state.state && state.state.theme) || 'light';
    var lang  = (state.state && state.state.language) || 'en';
    document.documentElement.classList.toggle('dark',  theme === 'dark');
    document.documentElement.classList.toggle('light', theme === 'light');
    document.documentElement.lang = lang;
  } catch (e) {}
})();
`.trim();

export const metadata: Metadata = {
  title: "InsightX — AI Analytics Platform",
  description:
    "AI-powered business analytics for small and medium businesses. Upload your sales data and get instant insights, forecasts, and customer intelligence.",
  keywords: [
    "analytics",
    "business intelligence",
    "AI",
    "sales",
    "forecasting",
    "customer segmentation",
  ],
  openGraph: {
    title: "InsightX — AI Analytics Platform",
    description:
      "Turn your sales data into actionable insights with AI-powered analytics.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = cookies();
  const lang = cookieStore.get('insightx_lang')?.value || 'en';

  return (
    // suppressHydrationWarning: the anti-FOUC script mutates class/lang
    // before React hydrates, so React would otherwise warn about a mismatch.
    // dir is always "ltr" — layout never mirrors for Arabic (text-only i18n).
    <html lang={lang} dir="ltr" suppressHydrationWarning>
      <head>
        {/* Anti-FOUC: set theme/lang class before first paint */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="bg-surface dark:bg-[#0f0f1a] min-h-screen font-sans antialiased text-slate-800 dark:text-slate-200">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
