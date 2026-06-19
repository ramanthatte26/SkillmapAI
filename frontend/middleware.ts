import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { isTokenExpired } from '@/lib/utils';

// Routes that require authentication
const PROTECTED_PREFIXES = ['/dashboard', '/roadmaps'];

// Routes that authenticated users should not see
const AUTH_ROUTES = ['/login', '/register'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Read token from cookie (set on login) or check for it in headers
  // For MVP: we rely on a cookie named 'skillmap_token' set by the client
  const token = request.cookies.get('skillmap_token')?.value;
  const isLoggedOut = request.nextUrl.searchParams.get('logged_out') === 'true';

  const isProtected = PROTECTED_PREFIXES.some((prefix) =>
    pathname.startsWith(prefix)
  );
  const isAuthRoute = AUTH_ROUTES.some((route) => pathname.startsWith(route));

  // If explicit logout query parameter is passed, clear the cookie and allow the page to render
  if (isLoggedOut && isAuthRoute) {
    const response = NextResponse.next();
    response.cookies.delete('skillmap_token');
    return response;
  }

  const hasValidToken = token && !isTokenExpired(token);

  // Redirect unauthenticated users away from protected pages
  if (isProtected && !hasValidToken) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('from', pathname);
    const response = NextResponse.redirect(loginUrl);
    // Clean up invalid cookie if present
    if (token) {
      response.cookies.delete('skillmap_token');
    }
    return response;
  }

  // Redirect authenticated users away from login/register
  if (isAuthRoute && hasValidToken) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Run middleware on these routes only
  matcher: ['/dashboard', '/dashboard/:path*', '/roadmaps', '/roadmaps/:path*', '/login', '/register'],
};

