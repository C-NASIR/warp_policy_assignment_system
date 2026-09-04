import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { apiConfigured, getCurrentUser, getRootSetupStatus } from "@/lib/backend";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage() {
  if (!apiConfigured) redirect("/");
  const [setup, user] = await Promise.all([getRootSetupStatus(), getCurrentUser()]);
  if (setup.setup_required) redirect("/setup");
  if (user) redirect("/");
  return <AuthForm mode="login" />;
}
