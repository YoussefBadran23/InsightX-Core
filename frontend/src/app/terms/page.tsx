import Link from 'next/link';

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-surface flex flex-col font-sans text-text-primary">
      <header className="flex items-center justify-between px-8 py-6 border-b border-surface-border glass-nav">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-xl font-bold tracking-tight hover:text-primary transition-colors">
            InsightX
          </Link>
        </div>
      </header>
      <main className="flex-1 max-w-4xl mx-auto w-full p-8 md:p-16">
        <h1 className="text-4xl font-bold mb-6">Terms of Service</h1>
        <div className="card space-y-6">
          <p className="text-sm text-text-muted">Last Updated: April 2026</p>
          <section>
            <h2 className="text-2xl font-semibold mb-3">1. Acceptance of Terms</h2>
            <p className="text-text-secondary leading-relaxed">
              By accessing and using InsightX, you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use our platform.
            </p>
          </section>
          <section>
            <h2 className="text-2xl font-semibold mb-3">2. Description of Service</h2>
            <p className="text-text-secondary leading-relaxed">
              InsightX provides AI-powered business analytics, forecasting, and data processing services. We reserve the right to modify or discontinue the service at any time.
            </p>
          </section>
          <section>
            <h2 className="text-2xl font-semibold mb-3">3. User Data</h2>
            <p className="text-text-secondary leading-relaxed">
              You retain all rights to the data you upload. InsightX only processes your data to provide analytics and insights directly to you, and does not share your raw data with third parties.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
