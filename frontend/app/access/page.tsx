import type { Metadata } from "next";
import { AccessManager } from "@/components/access-manager";
import { apiConfigured, getAuthorizationAssignmentFields, getCurrentUser, getEmployees, getPermissions, getRoles, getUsers } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Access control" };

export default async function AccessPage() {
  const currentUser = await getCurrentUser();
  const canReadEmployees = hasPermission(currentUser, "employees:read");
  const [permissions, assignmentFields, roles, users, employees] = await Promise.all([
    getPermissions(),
    getAuthorizationAssignmentFields(),
    getRoles(),
    getUsers(),
    canReadEmployees ? getEmployees() : Promise.resolve([]),
  ]);
  return <AccessManager initialUsers={users} initialRoles={roles} employees={employees} permissions={permissions} assignmentFields={assignmentFields} canManage={hasPermission(currentUser, "access:manage")} canReadEmployees={canReadEmployees} apiConfigured={apiConfigured} />;
}
