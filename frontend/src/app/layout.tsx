import type { Metadata } from "next";
import { init } from "@sentry/nextjs";
import "./globals.css";

// Initialize Sentry
if (typeof window !== 'undefined') {
  init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    environment: process.env.NODE_ENV,
    tracesSampleRate: 1.0,
  });
}

export const metadata: Metadata = {
  title: "InsightX — AI Analytics Platform",
  description: "AI-powered business analytics for small and medium businesses. Upload your sales data and get instant insights, forecasts, and customer intelligence.",
  keywords: ["analytics", "business intelligence", "AI", "sales", "forecasting", "customer segmentation"],
  openGraph: {
    title: "InsightX — AI Analytics Platform",
    description: "Turn your sales data into actionable insights with AI-powered analytics.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="light">
      <body className="bg-surface min-h-screen font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
