import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { SetupForm } from "@/components/features/auth";
import { getCurrentUser, getRootSetupStatus } from "@/lib/backend";
import { firstAllowedPath } from "@/lib/permissions";

export const metadata: Metadata = { title: "Workspace setup" };

export default async function SetupPage() {
  const user = await getCurrentUser();
  if (user) redirect(firstAllowedPath(user));
  const setup = await getRootSetupStatus();
  if (!setup.setup_required) redirect("/signup");
  return <SetupForm />;
}
