import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { LoginForm } from "@/components/features/auth";
import { getCurrentUser } from "@/lib/backend";
import { firstAllowedPath } from "@/lib/permissions";

export const metadata: Metadata = { title: "Sign in" };

function safeNext(value: string | string[] | undefined): string | undefined {
  const candidate = Array.isArray(value) ? value[0] : value;
  return candidate?.startsWith("/") && !candidate.startsWith("//") ? candidate : undefined;
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const nextPath = safeNext((await searchParams).next);
  const user = await getCurrentUser();
  if (user) redirect(nextPath ?? firstAllowedPath(user));
  return <LoginForm nextPath={nextPath} />;
}
