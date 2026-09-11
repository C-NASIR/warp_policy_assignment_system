import { NextRequest } from "next/server";

const apiUrl = process.env.POLICY_API_URL?.replace(/\/$/, "");
const sessionCookieName = "policyos_session";

function hasTrustedOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host) return false;
  try {
    const parsedOrigin = new URL(origin);
    const forwardedProtocol = request.headers.get("x-forwarded-proto")?.split(",")[0].trim();
    const expectedProtocol = forwardedProtocol || request.nextUrl.protocol.replace(":", "");
    return parsedOrigin.host === host && parsedOrigin.protocol === `${expectedProtocol}:`;
  } catch {
    return false;
  }
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (!apiUrl) {
    return Response.json(
      {
        error: {
          code: "backend_not_configured",
          message: "POLICY_API_URL is required to connect the frontend to PolicyOS.",
        },
      },
      { status: 503 },
    );
  }

  const { path } = await context.params;
  const target = new URL(path.map(encodeURIComponent).join("/"), `${apiUrl}/`);
  target.search = request.nextUrl.search;
  const safeMethod = ["GET", "HEAD", "OPTIONS"].includes(request.method);
  const body = safeMethod ? undefined : await request.text();
  const sessionToken = request.cookies.get(sessionCookieName)?.value;
  if (!safeMethod && !hasTrustedOrigin(request)) {
    return Response.json(
      {
        error: {
          code: "untrusted_origin",
          message: "This request did not originate from PolicyOS.",
        },
      },
      { status: 403 },
    );
  }
  const response = await fetch(target, {
    method: request.method,
    headers: {
      Accept: "application/json",
      ...(sessionToken ? { Cookie: `${sessionCookieName}=${sessionToken}` } : {}),
      ...(request.headers.get("origin") ? { Origin: request.headers.get("origin")! } : {}),
      ...(request.headers.get("user-agent")
        ? { "User-Agent": request.headers.get("user-agent")!.slice(0, 500) }
        : {}),
      ...(body
        ? { "Content-Type": request.headers.get("content-type") ?? "application/json" }
        : {}),
    },
    body,
    cache: "no-store",
  });

  const headers = new Headers();
  for (const name of [
    "content-type",
    "x-total-count",
    "x-limit",
    "x-offset",
    "www-authenticate",
    "set-cookie",
  ]) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(response.body, { status: response.status, headers });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
