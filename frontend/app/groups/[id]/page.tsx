import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { notFound } from "next/navigation";
import { GroupManager } from "@/components/group-manager";
import {
  apiConfigured,
  getCurrentUser,
  getEmployees,
  getGroup,
  getGroupEmployees,
  getGroupPolicies,
  getPolicies,
} from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export async function generateMetadata({ params }: PageProps<"/groups/[id]">): Promise<Metadata> {
  const { id } = await params;
  const group = await getGroup(Number(id));
  return {
    title: group?.name ?? "Group",
    description: group ? `Members and policies for ${group.name}` : "Group details",
    openGraph: { images: [] },
    twitter: { images: [] },
  };
}

export default async function GroupDetailPage({ params }: PageProps<"/groups/[id]">) {
  const { id } = await params;
  const groupId = Number(id);
  const user = await getCurrentUser();
  const [group, members, attachedPolicies, employees, policies] = await Promise.all([
    getGroup(groupId),
    getGroupEmployees(groupId),
    getGroupPolicies(groupId),
    !apiConfigured || hasPermission(user, "employees:read") ? getEmployees() : [],
    !apiConfigured || hasPermission(user, "policies:read") ? getPolicies() : [],
  ]);
  if (!group) notFound();
  return (
    <>
      <Link className="page-back-link" href="/groups">
        <ArrowLeft size={13} />
        Back to groups
      </Link>
      <GroupManager
        group={group}
        initialMembers={members}
        initialPolicies={attachedPolicies}
        employees={employees}
        policies={policies}
        apiConfigured={apiConfigured}
        canManage={hasPermission(user, "groups:update")}
      />
    </>
  );
}
