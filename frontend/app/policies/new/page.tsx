import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { PolicyBuilder } from "@/components/policy-builder";
import { apiConfigured, getAssignmentFields, getConditionFields, getEmployees, getPolicy } from "@/lib/backend";

export const metadata: Metadata = { title: "Create policy" };

export default async function NewPolicyPage({ searchParams }: PageProps<"/policies/new">) {
  const { policyId } = await searchParams;
  const id = typeof policyId === "string" ? Number(policyId) : null;
  const [conditionFields, assignmentFields, employees, basePolicy] = await Promise.all([getConditionFields(), getAssignmentFields(), getEmployees(), id ? getPolicy(id) : null]);
  return <><div className="breadcrumb"><Link href="/policies">Policies</Link><ChevronRight size={11} /><span>{basePolicy ? `New ${basePolicy.name} version` : "Create policy"}</span></div><div className="page-heading"><div><p className="eyebrow">Policy authoring</p><h1>{basePolicy ? "Create a new version" : "Create a policy"}</h1><p className="page-subtitle">Define the population, assignments, priority, and effective dates. Review the impact before anything changes.</p></div><span className="badge accent">Draft</span></div><PolicyBuilder conditionFields={conditionFields} assignmentFields={assignmentFields} employees={employees} apiConfigured={apiConfigured} basePolicy={basePolicy} /></>;
}
