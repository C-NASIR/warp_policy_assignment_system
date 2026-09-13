import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { redirect } from "next/navigation";
import { PolicyBuilder } from "./_components/policy-builder/policy-builder";
import { Badge } from "@/components/ui";
import {
  getAssignmentFields,
  getConditionFields,
  getCurrentUser,
  getEmployeeReferenceData,
  getEmployees,
  getPolicy,
} from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Create policy" };

export default async function NewPolicyPage({ searchParams }: PageProps<"/policies/new">) {
  const { policyId } = await searchParams;
  const id = typeof policyId === "string" ? Number(policyId) : null;
  const user = await getCurrentUser();
  const [conditionFields, assignmentFields, employees, referenceData, basePolicy] =
    await Promise.all([
      getConditionFields(),
      getAssignmentFields(),
      getEmployees(),
      getEmployeeReferenceData(),
      id ? getPolicy(id) : null,
    ]);
  if (id ? !basePolicy?.capabilities.can_create_version : !hasPermission(user, "policies:create"))
    redirect("/forbidden");
  const activateOnCreate =
    hasPermission(user, "policies:activate") || hasPermission(user, "policies:update");
  return (
    <>
      <div className="breadcrumb">
        <Link href="/policies">Policies</Link>
        <ChevronRight size={11} />
        <span>{basePolicy ? `New ${basePolicy.name} version` : "Create policy"}</span>
      </div>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Policy authoring</p>
          <h1>{basePolicy ? "Create a new version" : "Create a policy"}</h1>
          <p className="page-subtitle">
            Define the population, employee assignments, priority, and effective dates. Review the
            impact before anything changes.
          </p>
        </div>
        <Badge tone="accent">Draft</Badge>
      </div>
      <PolicyBuilder
        conditionFields={conditionFields}
        assignmentFields={assignmentFields}
        employees={employees}
        referenceData={referenceData}
        basePolicy={basePolicy}
        activateOnCreate={activateOnCreate}
      />
    </>
  );
}
