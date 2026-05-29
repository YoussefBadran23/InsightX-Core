'use client';

import { useEffect } from 'react';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to error tracking (Sentry is already configured via api.ts interceptor)
  }, [error]);

  return (
    <div className="flex-1 p-8 flex flex-col items-center justify-center gap-4 h-full">
      <p className="text-red-500 font-semibold">Something went wrong loading this page.</p>
      <button
        onClick={reset}
        className="btn btn-primary btn-sm"
      >
        Try again
      </button>
    </div>
  );
}
