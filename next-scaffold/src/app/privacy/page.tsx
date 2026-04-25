import Link from 'next/link';

export default function PrivacyPage() {
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
        <h1 className="text-4xl font-bold mb-6">Privacy Policy</h1>
        <div className="card space-y-6">
          <p className="text-sm text-text-muted">Last Updated: April 2026</p>
          <section>
            <h2 className="text-2xl font-semibold mb-3">1. Information We Collect</h2>
            <p className="text-text-secondary leading-relaxed">
              We collect information you provide directly to us, such as when you create an account, update your profile, or upload datasets for analysis.
            </p>
          </section>
          <section>
            <h2 className="text-2xl font-semibold mb-3">2. How We Use Information</h2>
            <p className="text-text-secondary leading-relaxed">
              We use the information we collect to provide, maintain, and improve our services, to process transactions, and to send you related information including confirmations and technical notices.
            </p>
          </section>
          <section>
            <h2 className="text-2xl font-semibold mb-3">3. Data Security</h2>
            <p className="text-text-secondary leading-relaxed">
              We take reasonable measures to help protect information about you from loss, theft, misuse, unauthorized access, disclosure, alteration, and destruction.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
