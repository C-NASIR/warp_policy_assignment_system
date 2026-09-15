import { NextRequest, NextResponse } from "next/server";

const sessionCookieName = "policyos_session";
const publicPaths = new Set(["/", "/login", "/signup", "/setup", "/recover"]);

function isPublicPath(pathname: string) {
  return publicPaths.has(pathname) || pathname === "/learn" || pathname.startsWith("/learn/");
}

export function proxy(request: NextRequest) {
  if (!process.env.POLICY_API_URL || isPublicPath(request.nextUrl.pathname)) {
    return NextResponse.next();
  }
  if (request.cookies.has(sessionCookieName)) return NextResponse.next();

  const login = new URL("/login", request.url);
  login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|og.png|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
