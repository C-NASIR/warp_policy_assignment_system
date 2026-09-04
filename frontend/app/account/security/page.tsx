import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { SecurityForm } from "@/components/security-form";
import { getAccountSecurity, getCurrentUser } from "@/lib/backend";

export const metadata: Metadata = { title: "Account security" };

export default async function AccountSecurityPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  const security = await getAccountSecurity();
  return <><div className="page-heading"><div><p className="eyebrow">Your account</p><h1>Security</h1><p className="page-subtitle">Signed in as {user.email}. Manage identity verification, devices, and security activity.</p></div><span className="badge success">{user.is_root ? "Root account" : "Active account"}</span></div><SecurityForm initialSecurity={security} /></>;
}
