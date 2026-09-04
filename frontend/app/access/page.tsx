import type { Metadata } from "next";
import { AccessManager } from "@/components/access-manager";
import { apiConfigured, getCurrentUser, getPermissions, getRoles, getUsers } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Access control" };

export default async function AccessPage() {
  const [currentUser, permissions, roles, users] = await Promise.all([
    getCurrentUser(),
    getPermissions(),
    getRoles(),
    getUsers(),
  ]);
  return <AccessManager initialUsers={users} initialRoles={roles} permissions={permissions} canManage={hasPermission(currentUser, "access:manage")} apiConfigured={apiConfigured} />;
}
