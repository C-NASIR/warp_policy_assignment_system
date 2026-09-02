import type { Metadata } from "next";
import { ScrollText } from "lucide-react";
import { getAuditLogs } from "@/lib/backend";
import { formatDate, titleCase } from "@/lib/format";

export const metadata: Metadata = { title: "Audit log" };

export default async function AuditPage() {
  const events = await getAuditLogs();
  return <><div className="page-heading"><div><p className="eyebrow">Accountability</p><h1>Audit log</h1><p className="page-subtitle">A chronological record of policy, employee, assignment, and override changes.</p></div><span className="badge accent"><ScrollText size={11} /> Append-only</span></div><div className="data-panel"><table className="data-table"><thead><tr><th>When</th><th>Actor</th><th>Entity</th><th>Action</th><th>Change</th></tr></thead><tbody>{events.map((event) => <tr key={event.id}><td>{formatDate(event.timestamp)}</td><td><span className="primary-cell">{event.actor}</span></td><td>{event.entity_type} #{event.entity_id}</td><td><span className={`badge ${event.action === "created" ? "success" : "accent"}`}>{titleCase(event.action)}</span></td><td><span className="secondary-cell" style={{ margin: 0 }}>{summarizeChange(event.before, event.after)}</span></td></tr>)}</tbody></table><div className="pagination-footer"><span>{events.length} recent events</span><span>All times shown in UTC</span></div></div></>;
}

function summarizeChange(before: Record<string, unknown> | null, after: Record<string, unknown> | null) {
  if (!before && after) return Object.entries(after).slice(0, 2).map(([key, value]) => `${titleCase(key)}: ${String(value)}`).join(" · ");
  if (before && after) { const key = Object.keys(after).find((item) => before[item] !== after[item]); return key ? `${titleCase(key)}: ${String(before[key])} → ${String(after[key])}` : "Metadata updated"; }
  return "Record closed";
}
