import type { Metadata } from "next";
import { AssignmentFieldManager } from "@/components/features/settings";
import { getAssignmentFields, getCurrentUser } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Assignment fields" };

export default async function SettingsPage() {
  const [fields, user] = await Promise.all([getAssignmentFields(), getCurrentUser()]);
  return (
    <AssignmentFieldManager
      initialFields={fields}
      canManage={hasPermission(user, "settings:manage")}
    />
  );
}
