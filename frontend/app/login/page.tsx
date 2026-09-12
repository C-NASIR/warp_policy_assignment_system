import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { LoginForm } from "@/components/features/auth";
import { getCurrentUser } from "@/lib/backend";
import { firstAllowedPath } from "@/lib/permissions";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage() {
  const user = await getCurrentUser();
  if (user) redirect(firstAllowedPath(user));
  return <LoginForm />;
}
