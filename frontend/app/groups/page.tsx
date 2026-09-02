import type { Metadata } from "next";
import { GroupDirectory } from "@/components/group-directory";
import { apiConfigured, getGroupEmployees, getGroupPolicies, getGroups } from "@/lib/backend";

export const metadata: Metadata = { title: "Groups" };

export default async function GroupsPage() {
  const groups = await getGroups();
  const rows = await Promise.all(groups.map(async (group) => {
    const [members, policies] = await Promise.all([getGroupEmployees(group.id), getGroupPolicies(group.id)]);
    return { ...group, memberCount: members.length, policyCount: policies.length };
  }));
  return <GroupDirectory initialGroups={rows} apiConfigured={apiConfigured} />;
}
