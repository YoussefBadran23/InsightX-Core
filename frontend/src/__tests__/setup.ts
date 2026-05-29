import '@testing-library/jest-dom';

// Provide a functional localStorage because jsdom's is broken when
// --localstorage-file is passed without a valid path (Zustand persist middleware uses it)
const _storage: Record<string, string> = {};
const localStorageMock: Storage = {
  getItem: (key) => _storage[key] ?? null,
  setItem: (key, value) => { _storage[key] = String(value); },
  removeItem: (key) => { delete _storage[key]; },
  clear: () => { Object.keys(_storage).forEach((k) => delete _storage[k]); },
  get length() { return Object.keys(_storage).length; },
  key: (index) => Object.keys(_storage)[index] ?? null,
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock, writable: true, configurable: true });

vi.mock('@sentry/nextjs', () => ({
  captureException: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/',
}));
