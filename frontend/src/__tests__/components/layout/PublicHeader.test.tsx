import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

const mockToggleTheme = vi.fn();
const mockSetLanguage = vi.fn();

const { mockUseAuthStore, mockUseUiStore } = vi.hoisted(() => ({
  mockUseAuthStore: vi.fn(),
  mockUseUiStore: vi.fn(),
}));

vi.mock('@/stores/authStore', () => ({ useAuthStore: mockUseAuthStore }));
vi.mock('@/stores/uiStore', () => ({ useUiStore: mockUseUiStore }));

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode; [k: string]: unknown }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { PublicHeader } from '@/components/layout/PublicHeader';

const unauthState = { isAuthenticated: false, token: null, user: null };
const uiState = { theme: 'light' as const, language: 'en' as const, toggleTheme: mockToggleTheme, setLanguage: mockSetLanguage };

describe('PublicHeader (unauthenticated)', () => {
  beforeEach(() => {
    mockToggleTheme.mockClear();
    mockSetLanguage.mockClear();
    mockUseAuthStore.mockReturnValue(unauthState);
    mockUseUiStore.mockReturnValue(uiState);
  });

  it('renders the InsightX brand name', () => {
    render(<PublicHeader />);
    // Brand is split "Insight" + "X" across two spans; match the containing link
    expect(screen.getByRole('link', { name: /insight/i })).toBeInTheDocument();
  });

  it('shows Login and Sign Up links when not authenticated', () => {
    render(<PublicHeader />);
    expect(screen.getByText('Login')).toBeInTheDocument();
    expect(screen.getByText('Sign Up')).toBeInTheDocument();
  });

  it('calls toggleTheme when theme button is clicked', () => {
    render(<PublicHeader />);
    const btn = screen.getByLabelText(/toggle theme/i);
    fireEvent.click(btn);
    expect(mockToggleTheme).toHaveBeenCalledOnce();
  });

  it('opens the language dropdown on Globe button click', () => {
    render(<PublicHeader />);
    const langBtn = screen.getByLabelText(/language/i);
    fireEvent.click(langBtn);
    expect(screen.getByText('English')).toBeInTheDocument();
    expect(screen.getByText('العربية')).toBeInTheDocument();
  });

  it('calls setLanguage with ar when Arabic option is clicked', () => {
    render(<PublicHeader />);
    fireEvent.click(screen.getByLabelText(/language/i));
    fireEvent.click(screen.getByText('العربية'));
    expect(mockSetLanguage).toHaveBeenCalledWith('ar');
  });
});

describe('PublicHeader (authenticated)', () => {
  beforeEach(() => {
    mockUseAuthStore.mockReturnValue({ isAuthenticated: true, token: 'tok', user: null });
    mockUseUiStore.mockReturnValue(uiState);
  });

  afterEach(() => {
    mockUseAuthStore.mockReturnValue(unauthState);
  });

  it('shows View Dashboard link instead of Login/Sign Up', () => {
    render(<PublicHeader />);
    expect(screen.getByText(/view dashboard/i)).toBeInTheDocument();
    expect(screen.queryByText('Login')).not.toBeInTheDocument();
  });
});
