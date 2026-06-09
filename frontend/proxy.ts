import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Optimistic session check: look for any Supabase auth token cookie.
// Real auth verification happens in individual Server Components via getUser().
function hasSessionCookie(request: NextRequest): boolean {
  const cookieName = `sb-${
    process.env.NEXT_PUBLIC_SUPABASE_URL?.match(/\/\/([^.]+)\./)?.[1] ?? ""
  }-auth-token`;
  // Supabase can also split the token across numbered chunks
  return (
    request.cookies.has(cookieName) ||
    request.cookies.has(`${cookieName}.0`)
  );
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isAuthRoute =
    pathname.startsWith("/login") || pathname.startsWith("/signup");

  const loggedIn = hasSessionCookie(request);

  if (!loggedIn && !isAuthRoute) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (loggedIn && isAuthRoute) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
