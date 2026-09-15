import type { Metadata } from "next";
import { AccessManager } from "./_components/access-manager/access-manager";
import { getCurrentUser, getRoleCandidate, getRolePage, getUserPage } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Access control" };

const userPageSize = 25;
const rolePageSize = 24;

export default async function AccessPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const tab = value(params.tab) === "roles" ? "roles" : "users";
  const search = value(params.search);
  const offset = nonnegativeInteger(value(params.offset));
  const status = value(params.status);
  const roleId = positiveInteger(value(params.role_id));
  const currentUserPromise = getCurrentUser();
  if (tab === "users") {
    const [currentUser, page, roleFilter] = await Promise.all([
      currentUserPromise,
      getUserPage({
        search,
        status: status || undefined,
        roleId,
        limit: userPageSize,
        offset,
      }),
      roleId ? getRoleCandidate(roleId) : Promise.resolve(null),
    ]);
    return (
      <AccessManager
        tab="users"
        userPage={page}
        filters={{ search, status, roleId }}
        initialRoleFilter={roleFilter}
        canManage={hasPermission(currentUser, "access:manage")}
        canReadEmployees={hasPermission(currentUser, "employees:read")}
        mfaEnabled={currentUser?.mfa_enabled ?? false}
      />
    );
  }

  const [currentUser, page] = await Promise.all([
    currentUserPromise,
    getRolePage({ search, limit: rolePageSize, offset }),
  ]);
  return (
    <AccessManager
      tab="roles"
      rolePage={page}
      filters={{ search, status: "" }}
      initialRoleFilter={null}
      canManage={hasPermission(currentUser, "access:manage")}
      canReadEmployees={hasPermission(currentUser, "employees:read")}
      mfaEnabled={currentUser?.mfa_enabled ?? false}
    />
  );
}

function value(input: string | string[] | undefined): string {
  return typeof input === "string" ? input : "";
}

function nonnegativeInteger(input: string): number {
  const parsed = Number(input);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function positiveInteger(input: string): number | undefined {
  const parsed = Number(input);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}
