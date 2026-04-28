import Link from 'next/link';

export default function SupportPage() {
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
        <h1 className="text-4xl font-bold mb-6">Help Center & Support</h1>
        <div className="card space-y-6">
          <section>
            <h2 className="text-2xl font-semibold mb-3">Contact Us</h2>
            <p className="text-text-secondary leading-relaxed">
              Need assistance with your data pipeline or analytics dashboard? Our team is here to help. 
              Please reach out to us at <a href="mailto:support@insightx.io" className="text-primary hover:underline">support@insightx.io</a> and we will respond within 24 hours.
            </p>
          </section>
          <section>
            <h2 className="text-2xl font-semibold mb-3">FAQ</h2>
            <div className="space-y-4">
              <div>
                <h3 className="font-medium text-lg">How long does data processing take?</h3>
                <p className="text-text-secondary text-sm mt-1">Depending on the size of your CSV, it may take anywhere from a few seconds to several minutes.</p>
              </div>
              <div>
                <h3 className="font-medium text-lg">Can I upload multiple datasets?</h3>
                <p className="text-text-secondary text-sm mt-1">Yes, you can initiate a new analysis from the dashboard anytime.</p>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
