import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const mockOnComplete = vi.fn();

// OnboardingModal is the entire upload page — mock it to a simple stub
vi.mock('@/components/OnboardingModal', () => ({
  OnboardingModal: ({ onComplete }: { onComplete: () => void }) => (
    <div>
      <span>Onboarding Modal</span>
      <button onClick={onComplete}>Complete</button>
    </div>
  ),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

describe('UploadPage', () => {
  it('renders the OnboardingModal', async () => {
    const UploadPage = (await import('@/app/dashboard/upload/page')).default;
    render(<UploadPage />);
    expect(screen.getByText('Onboarding Modal')).toBeInTheDocument();
  });

  it('redirects to /dashboard when onComplete fires', async () => {
    // Spy on window.location.href setter
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { href: '' },
    });

    const UploadPage = (await import('@/app/dashboard/upload/page')).default;
    const { getByText, fireEvent: fe } = await import('@testing-library/react');
    render(<UploadPage />);

    const btn = getByText(document.body, 'Complete');
    btn.click();

    expect(window.location.href).toBe('/dashboard');
    Object.defineProperty(window, 'location', {
      writable: true,
      value: originalLocation,
    });
  });
});
