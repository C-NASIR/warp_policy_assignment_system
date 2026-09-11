import type { Metadata } from "next";
import { AuditLogExplorer } from "@/components/audit-log-explorer";
import { getAuditLogFacets, getAuditLogPage } from "@/lib/backend";

export const metadata: Metadata = { title: "Audit log" };

const pageSize = 50;

export default async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const search = value(params.search);
  const entityType = value(params.entity_type);
  const action = value(params.action);
  const offset = nonnegativeInteger(value(params.offset));
  const [page, facets] = await Promise.all([
    getAuditLogPage({ search, entityType, action, limit: pageSize, offset }),
    getAuditLogFacets(),
  ]);
  return (
    <AuditLogExplorer
      events={page.items}
      facets={facets}
      total={page.total}
      limit={page.limit}
      offset={page.offset}
      filters={{ search, entityType, action }}
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
