import type { Metadata } from "next";
import Link from "next/link";
import { Plus } from "lucide-react";
import { PolicyDirectory } from "@/components/policy-directory";
import { getPolicies, getPolicyImpact } from "@/lib/backend";
import type { PolicyImpact } from "@/lib/types";

export const metadata: Metadata = { title: "Policies" };

export default async function PoliciesPage() {
  const policies = await getPolicies();
  const impactRows = await Promise.all(policies.map(async (policy) => [policy.id, await getPolicyImpact(policy.id)] as const));
  const impacts = Object.fromEntries(impactRows) as Record<number, PolicyImpact | null>;
  return <><div className="page-heading"><div><p className="eyebrow">Assignment rules</p><h1>Policies</h1><p className="page-subtitle">Define who receives what, resolve overlapping rules with priority, and understand every policy’s reach.</p></div><Link className="button" href="/policies/new"><Plus size={15} /> Create policy</Link></div><PolicyDirectory policies={policies} impacts={impacts} /></>;
}
