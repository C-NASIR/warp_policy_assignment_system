"use client";

import { ChevronDown, ChevronUp, Search, ScrollText } from "lucide-react";
import { useState } from "react";
import { formatDate, titleCase } from "@/lib/format";
import type { AuditLog, LearningInsights } from "@/lib/types";

export function AuditLogExplorer({ events, entityLabels, learningInsights }: { events: AuditLog[]; entityLabels: Record<number, string>; learningInsights: LearningInsights }) {
  const [search, setSearch] = useState("");
  const [entity, setEntity] = useState("all");
  const [action, setAction] = useState("all");
  const [expanded, setExpanded] = useState<number | null>(null);
  const entityTypes = [...new Set(events.map((event) => event.entity_type))].sort();
  const actions = [...new Set(events.map((event) => event.action))].sort();
  const filtered = events.filter((event) => {
    const haystack = `${event.actor} ${entityLabels[event.id]} ${event.entity_type} ${event.action} ${JSON.stringify(event.before)} ${JSON.stringify(event.after)}`.toLowerCase();
    return haystack.includes(search.toLowerCase()) && (entity === "all" || event.entity_type === entity) && (action === "all" || event.action === action);
  });

  return <><div className="page-heading"><div><p className="eyebrow">Accountability</p><h1>Audit log</h1><p className="page-subtitle">Trace who changed every policy, employee, group, assignment, and override.</p></div><span className="badge accent"><ScrollText size={11} /> Append-only</span></div><LearningSignals insights={learningInsights} /><div className="toolbar"><div className="toolbar-left"><label className="search-box"><Search size={14} /><input className="input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search actor or change" aria-label="Search audit log" /></label><select className="select filter-select" value={entity} onChange={(event) => setEntity(event.target.value)} aria-label="Filter by entity"><option value="all">All entities</option>{entityTypes.map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}</select><select className="select filter-select" value={action} onChange={(event) => setAction(event.target.value)} aria-label="Filter by action"><option value="all">All actions</option>{actions.map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}</select></div><span className="results-count">{filtered.length} events</span></div><div className="data-panel"><div className="audit-table-scroll"><table className="data-table audit-table"><colgroup><col className="audit-when-column" /><col className="audit-actor-column" /><col className="audit-entity-column" /><col className="audit-action-column" /><col /><col className="audit-details-column" /></colgroup><thead><tr><th>When</th><th>Actor</th><th>Entity</th><th>Action</th><th>Summary</th><th aria-label="Details" /></tr></thead><tbody>{filtered.map((event) => <AuditRow event={event} entityLabel={entityLabels[event.id] ?? titleCase(event.entity_type)} expanded={expanded === event.id} onToggle={() => setExpanded((current) => current === event.id ? null : event.id)} key={event.id} />)}</tbody></table>{filtered.length === 0 && <div className="empty-state compact">No audit events match those filters.</div>}</div><div className="pagination-footer"><span>{filtered.length} of {events.length} recent events</span><span>Newest first · UTC</span></div></div></>;
}

function LearningSignals({ insights }: { insights: LearningInsights }) {
  const topFeedback = insights.article_feedback.slice(0, 5);
  const misses = insights.unsuccessful_searches.slice(0, 5);
  return <section className="learning-signals" aria-labelledby="learning-signals-title"><div className="learning-signals-head"><div><p className="eyebrow">Learning quality</p><h2 id="learning-signals-title">Onboarding signals</h2></div><span className="badge">Aggregate only</span></div><div className="learning-signal-grid"><div className="learning-signal-score"><strong>{insights.helpful_percentage === null ? "—" : `${insights.helpful_percentage}%`}</strong><span>helpful</span><small>{insights.total_feedback} article responses</small></div><div><h3>Articles needing attention</h3>{topFeedback.length === 0 ? <p className="learning-signal-empty">No article feedback yet.</p> : <ol className="learning-signal-list">{topFeedback.map((item) => <li key={item.article_id}><span>{item.article_id}</span><small>{item.not_helpful_count} not yet · {item.helpful_count} helpful</small></li>)}</ol>}</div><div><h3>Unsuccessful Quick Find searches</h3>{misses.length === 0 ? <p className="learning-signal-empty">No zero-result searches yet.</p> : <ol className="learning-signal-list">{misses.map((item) => <li key={item.query}><span>{item.query}</span><small>{item.count} {item.count === 1 ? "miss" : "misses"} · last {formatDate(item.last_seen_at)}</small></li>)}</ol>}</div></div></section>;
}

function AuditRow({ event, entityLabel, expanded, onToggle }: { event: AuditLog; entityLabel: string; expanded: boolean; onToggle(): void }) {
  return <><tr><td><time className="audit-time" dateTime={event.timestamp}><span>{formatDate(event.timestamp)}</span><small>{formatAuditTime(event.timestamp)}</small></time></td><td><span className="primary-cell audit-actor" title={event.actor}>{event.actor}</span></td><td><span className="primary-cell">{entityLabel}</span><span className="secondary-cell">{titleCase(event.entity_type)}</span></td><td><span className={`badge ${event.action === "created" ? "success" : event.action === "deleted" ? "warning" : "accent"}`}>{titleCase(event.action)}</span></td><td><span className="audit-summary">{summarizeChange(event.before, event.after)}</span></td><td><button className="icon-button audit-expand-button" onClick={onToggle} aria-expanded={expanded} aria-label={expanded ? "Hide event payload" : "Show event payload"}>{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button></td></tr>{expanded && <tr className="audit-detail-row"><td colSpan={6}><div className="audit-record-reference">Technical reference · {event.entity_type} #{event.entity_id}</div><div className="audit-payload"><div><span className="label">Before</span><pre>{JSON.stringify(event.before, null, 2) || "None"}</pre></div><div><span className="label">After</span><pre>{JSON.stringify(event.after, null, 2) || "None"}</pre></div></div></td></tr>}</>;
}

function summarizeChange(before: Record<string, unknown> | null, after: Record<string, unknown> | null) {
  if (!before && after) return meaningfulEntries(after).slice(0, 2).map(([key, value]) => `${formatAuditKey(key)}: ${formatAuditValue(value)}`).join(" · ");
  if (before && after) { const key = meaningfulEntries(after).find(([item, value]) => before[item] !== value)?.[0]; return key ? `${formatAuditKey(key)}: ${formatAuditValue(before[key])} → ${formatAuditValue(after[key])}` : "Metadata updated"; }
  return "Record closed";
}

function meaningfulEntries(record: Record<string, unknown>) {
  const entries = Object.entries(record);
  const descriptive = entries.filter(([key]) => key !== "id" && !key.endsWith("_id") && !key.endsWith("_at"));
  const contextual = descriptive.filter(([key]) => key !== "name" && key !== "version_number");
  return contextual.length ? contextual : descriptive.length ? descriptive : entries;
}

function formatAuditKey(key: string) {
  return titleCase(key).replace(/\bId\b/g, "ID");
}

function formatAuditValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "None";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return `${value.length} ${value.length === 1 ? "item" : "items"}`;
  if (typeof value === "object") return "Details updated";
  return String(value);
}

function formatAuditTime(value: string) {
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "UTC" }).format(new Date(value));
}
