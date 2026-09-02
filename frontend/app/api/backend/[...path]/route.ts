import { NextRequest } from "next/server";

const apiUrl = process.env.POLICY_API_URL ?? "http://127.0.0.1:8000";
const apiToken = process.env.POLICY_API_TOKEN;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (!apiToken) {
    return Response.json({ error: { code: "demo_mode", message: "Connect POLICY_API_TOKEN to persist this change." } }, { status: 503 });
  }

  const { path } = await context.params;
  const target = new URL(path.map(encodeURIComponent).join("/"), `${apiUrl.replace(/\/$/, "")}/`);
  target.search = request.nextUrl.search;
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.text();
  const response = await fetch(target, {
    method: request.method,
    headers: {
      Authorization: `Bearer ${apiToken}`,
      Accept: "application/json",
      ...(body ? { "Content-Type": request.headers.get("content-type") ?? "application/json" } : {}),
    },
    body,
    cache: "no-store",
  });

  const headers = new Headers();
  for (const name of ["content-type", "x-total-count", "x-limit", "x-offset", "www-authenticate"]) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(response.body, { status: response.status, headers });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
