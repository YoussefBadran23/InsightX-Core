'use client';

/**
 * Standalone upload page. Renders the same multi-stage flow as the
 * first-time OnboardingModal so the UX is consistent and the user can
 * review column mappings + see which analytics modules will run before
 * confirming. Once the pipeline completes, we hard-reload to /dashboard
 * so every page picks up the fresh data.
 */

import { useRouter } from 'next/navigation';
import { OnboardingModal } from '@/components/OnboardingModal';

export default function UploadPage() {
  const router = useRouter();

  const handleComplete = () => {
    if (typeof window !== 'undefined') {
      window.location.href = '/dashboard';
    } else {
      router.push('/dashboard');
    }
  };

  return <OnboardingModal onComplete={handleComplete} />;
}
