import type { Metadata } from "next";
import { GroupDirectory } from "@/components/group-directory";
import { apiConfigured, getCurrentUser, getGroupEmployees, getGroupPolicies, getGroups } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Groups" };

export default async function GroupsPage() {
  const [groups, user] = await Promise.all([getGroups(), getCurrentUser()]);
  const rows = await Promise.all(groups.map(async (group) => {
    const [members, policies] = await Promise.all([getGroupEmployees(group.id), getGroupPolicies(group.id)]);
    return { ...group, memberCount: members.length, policyCount: policies.length };
  }));
  return <GroupDirectory initialGroups={rows} apiConfigured={apiConfigured} canCreate={hasPermission(user, "groups:create")} />;
}
