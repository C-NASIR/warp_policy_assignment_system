import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { SignupForm } from "@/components/features/auth";
import { getCurrentUser, getRootSetupStatus } from "@/lib/backend";
import { firstAllowedPath } from "@/lib/permissions";

export const metadata: Metadata = { title: "Sign up" };

export default async function SignupPage() {
  const user = await getCurrentUser();
  if (user) redirect(firstAllowedPath(user));
  const setup = await getRootSetupStatus();
  if (setup.setup_required) redirect("/setup");
  return <SignupForm />;
}
