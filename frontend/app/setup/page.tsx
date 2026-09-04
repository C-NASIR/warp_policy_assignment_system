import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { apiConfigured, getCurrentUser, getRootSetupStatus } from "@/lib/backend";

export const metadata: Metadata = { title: "Initialize workspace" };

export default async function SetupPage() {
  if (!apiConfigured) redirect("/");
  const [setup, user] = await Promise.all([getRootSetupStatus(), getCurrentUser()]);
  if (user) redirect("/");
  if (!setup.setup_required) redirect("/login");
  return <AuthForm mode="setup" />;
}
