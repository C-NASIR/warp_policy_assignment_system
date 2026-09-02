"use client";

import Link from "next/link";
import { BookOpenCheck, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { formatDate } from "@/lib/format";
import type { Policy, PolicyImpact } from "@/lib/types";

export function PolicyDirectory({ policies, impacts }: { policies: Policy[]; impacts: Record<number, PolicyImpact | null> }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("active");
  const filtered = useMemo(() => policies.filter((policy) => policy.name.toLowerCase().includes(search.toLowerCase()) && (status === "all" || policy.status === status)), [policies, search, status]);
  return <>
    <div className="toolbar"><div className="toolbar-left"><label className="search-box"><Search size={14} /><input className="input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search policies" aria-label="Search policies" /></label><select className="select filter-select" value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter by policy status"><option value="all">All statuses</option><option value="active">Active</option><option value="archived">Archived</option></select></div><div className="results-count">{filtered.length} policies</div></div>
    <div className="data-panel">{filtered.length ? <table className="data-table"><thead><tr><th>Policy</th><th>Rule</th><th>Priority</th><th>Effective</th><th>Impact</th><th>Status</th></tr></thead><tbody>{filtered.map((policy) => {
      const version = policy.versions.at(-1); const impact = impacts[policy.id]; const firstCondition = version?.condition_group.conditions[0];
      return <tr key={policy.id}><td><Link href={`/policies/${policy.id}`}><span className="primary-cell">{policy.name}</span><span className="secondary-cell">Version {version?.version_number ?? "—"}</span></Link></td><td>{firstCondition ? <span>{firstCondition.field.replaceAll("_", " ")} {firstCondition.operator} <strong>{firstCondition.value}</strong></span> : "No current rule"}</td><td><span className="badge">P{version?.priority ?? "—"}</span></td><td>{formatDate(version?.effective_from)}</td><td><span className="primary-cell">{impact?.selected_employee_count ?? 0}</span><span className="secondary-cell">employees selected</span></td><td><span className={`badge ${policy.status === "active" ? "success" : ""}`}>{policy.status === "active" ? "Active" : "Archived"}</span></td></tr>;
    })}</tbody></table> : <div className="empty-state"><div className="empty-icon"><BookOpenCheck size={18} /></div>No policies match those filters.</div>}<div className="pagination-footer"><span>Showing {filtered.length} of {policies.length}</span><span>Priority determines single-value winners</span></div></div>
  </>;
}
