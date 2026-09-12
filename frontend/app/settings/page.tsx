import type { Metadata } from "next";
import { AssignmentFieldManager } from "./_components/assignment-field-manager/assignment-field-manager";
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
