"use client";

import { ChevronDown, ChevronUp, Search, ScrollText } from "lucide-react";
import { useState } from "react";
import { formatDate, titleCase } from "@/lib/format";
import type { AuditLog } from "@/lib/types";

export function AuditLogExplorer({ events }: { events: AuditLog[] }) {
  const [search, setSearch] = useState("");
  const [entity, setEntity] = useState("all");
  const [action, setAction] = useState("all");
  const [expanded, setExpanded] = useState<number | null>(null);
  const entityTypes = [...new Set(events.map((event) => event.entity_type))].sort();
  const actions = [...new Set(events.map((event) => event.action))].sort();
  const filtered = events.filter((event) => {
    const haystack = `${event.actor} ${event.entity_type} ${event.action} ${JSON.stringify(event.before)} ${JSON.stringify(event.after)}`.toLowerCase();
    return haystack.includes(search.toLowerCase()) && (entity === "all" || event.entity_type === entity) && (action === "all" || event.action === action);
  });

  return <><div className="page-heading"><div><p className="eyebrow">Accountability</p><h1>Audit log</h1><p className="page-subtitle">Trace who changed every policy, employee, group, assignment, and override.</p></div><span className="badge accent"><ScrollText size={11} /> Append-only</span></div><div className="toolbar"><div className="toolbar-left"><label className="search-box"><Search size={14} /><input className="input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search actor or change" aria-label="Search audit log" /></label><select className="select filter-select" value={entity} onChange={(event) => setEntity(event.target.value)} aria-label="Filter by entity"><option value="all">All entities</option>{entityTypes.map((item) => <option key={item} value={item}>{item}</option>)}</select><select className="select filter-select" value={action} onChange={(event) => setAction(event.target.value)} aria-label="Filter by action"><option value="all">All actions</option>{actions.map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}</select></div><span className="results-count">{filtered.length} events</span></div><div className="data-panel"><table className="data-table audit-table"><thead><tr><th>When</th><th>Actor</th><th>Entity</th><th>Action</th><th>Summary</th><th aria-label="Details" /></tr></thead><tbody>{filtered.map((event) => <AuditRow event={event} expanded={expanded === event.id} onToggle={() => setExpanded((current) => current === event.id ? null : event.id)} key={event.id} />)}</tbody></table>{filtered.length === 0 && <div className="empty-state compact">No audit events match those filters.</div>}<div className="pagination-footer"><span>{filtered.length} of {events.length} recent events</span><span>All times shown in UTC</span></div></div></>;
}

function AuditRow({ event, expanded, onToggle }: { event: AuditLog; expanded: boolean; onToggle(): void }) {
  return <><tr><td>{formatDate(event.timestamp)}</td><td><span className="primary-cell">{event.actor}</span></td><td>{event.entity_type} #{event.entity_id}</td><td><span className={`badge ${event.action === "created" ? "success" : event.action === "deleted" ? "warning" : "accent"}`}>{titleCase(event.action)}</span></td><td><span className="secondary-cell" style={{ margin: 0 }}>{summarizeChange(event.before, event.after)}</span></td><td><button className="icon-button" onClick={onToggle} aria-label={expanded ? "Hide event payload" : "Show event payload"}>{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button></td></tr>{expanded && <tr className="audit-detail-row"><td colSpan={6}><div className="audit-payload"><div><span className="label">Before</span><pre>{JSON.stringify(event.before, null, 2) || "None"}</pre></div><div><span className="label">After</span><pre>{JSON.stringify(event.after, null, 2) || "None"}</pre></div></div></td></tr>}</>;
}

function summarizeChange(before: Record<string, unknown> | null, after: Record<string, unknown> | null) {
  if (!before && after) return Object.entries(after).slice(0, 2).map(([key, value]) => `${titleCase(key)}: ${String(value)}`).join(" · ");
  if (before && after) { const key = Object.keys(after).find((item) => before[item] !== after[item]); return key ? `${titleCase(key)}: ${String(before[key])} → ${String(after[key])}` : "Metadata updated"; }
  return "Record closed";
}
