import { NextRequest, NextResponse } from "next/server";

const sessionCookieName = "policyos_session";
const publicPaths = new Set(["/login", "/setup", "/recover"]);

export function proxy(request: NextRequest) {
  if (!process.env.POLICY_API_URL || publicPaths.has(request.nextUrl.pathname)) {
    return NextResponse.next();
  }
  if (request.cookies.has(sessionCookieName)) return NextResponse.next();

  const login = new URL("/login", request.url);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|og.png|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
