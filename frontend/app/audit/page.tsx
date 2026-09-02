import type { Metadata } from "next";
import { AuditLogExplorer } from "@/components/audit-log-explorer";
import { getAuditLogs } from "@/lib/backend";

export const metadata: Metadata = { title: "Audit log" };

export default async function AuditPage() {
  const events = await getAuditLogs();
  return <AuditLogExplorer events={events} />;
}
