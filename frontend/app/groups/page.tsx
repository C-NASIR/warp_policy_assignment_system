import type { Metadata } from "next";
import { GroupDirectory } from "@/components/group-directory";
import { getCurrentUser, getGroupPage } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Groups" };

const pageSize = 50;

export default async function GroupsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const search = value(params.search);
  const offset = nonnegativeInteger(value(params.offset));
  const [page, user] = await Promise.all([
    getGroupPage({ search, limit: pageSize, offset }),
    getCurrentUser(),
  ]);
  return (
    <GroupDirectory
      initialGroups={page.items}
      canCreate={hasPermission(user, "groups:create")}
      total={page.total}
      limit={page.limit}
      offset={page.offset}
      searchFilter={search}
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
