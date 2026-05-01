import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Protect all dashboard routes
const PROTECTED_PATHS = ['/dashboard'];
const AUTH_PATHS = ['/login', '/signup', '/forgot-password', '/reset-password'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token =
    request.cookies.get('insightx_token')?.value ||
    request.headers.get('authorization')?.replace('Bearer ', '');

  const isProtected = PROTECTED_PATHS.some((p) => pathname.startsWith(p));
  const isAuthPath  = AUTH_PATHS.some((p) => pathname.startsWith(p));
  const isRoot      = pathname === '/';

  // ── 1. Root path: redirect authenticated users straight to dashboard ──────
  if (isRoot && token) {
    const url = request.nextUrl.clone();
    url.pathname = '/dashboard';
    return NextResponse.redirect(url);
  }

  // ── 2. Protected routes: redirect unauthenticated users to login ──────────
  if (isProtected && !token) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    url.searchParams.set('from', pathname);
    return NextResponse.redirect(url);
  }

  // ── 3. Auth pages: redirect already-authenticated users to dashboard ───────
  if (isAuthPath && token) {
    const url = request.nextUrl.clone();
    url.pathname = '/dashboard';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/',                   // ← NEW: check root for auth-redirect
    '/dashboard/:path*',
    '/login',
    '/signup',
    '/forgot-password',
    '/reset-password',
  ],
};
