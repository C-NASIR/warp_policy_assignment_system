"use client";

import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown, BookOpenCheck, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { formatDate } from "@/lib/format";
import type { Policy, PolicyImpact } from "@/lib/types";

export function PolicyDirectory({ policies, impacts }: { policies: Policy[]; impacts: Record<number, PolicyImpact | null> }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("active");
  const [sort, setSort] = useState<{ key: "name" | "priority" | "effective" | "impact" | "status"; direction: "asc" | "desc" }>({ key: "name", direction: "asc" });
  const filtered = useMemo(() => policies.filter((policy) => policy.name.toLowerCase().includes(search.toLowerCase()) && (status === "all" || policy.status === status)), [policies, search, status]);
  const sorted = [...filtered].sort((left, right) => {
    const leftVersion = left.versions.at(-1); const rightVersion = right.versions.at(-1);
    const values = {
      name: [left.name, right.name], priority: [leftVersion?.priority ?? 0, rightVersion?.priority ?? 0], effective: [leftVersion?.effective_from ?? "", rightVersion?.effective_from ?? ""], impact: [impacts[left.id]?.selected_employee_count ?? 0, impacts[right.id]?.selected_employee_count ?? 0], status: [left.status, right.status],
    }[sort.key];
    const result = typeof values[0] === "number" ? Number(values[0]) - Number(values[1]) : String(values[0]).localeCompare(String(values[1]));
    return result * (sort.direction === "asc" ? 1 : -1);
  });
  function toggleSort(key: typeof sort.key) { setSort((current) => current.key === key ? { key, direction: current.direction === "asc" ? "desc" : "asc" } : { key, direction: "asc" }); }
  return <>
    <div className="toolbar"><div className="toolbar-left"><label className="search-box"><Search size={14} /><input className="input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search policies" aria-label="Search policies" /></label><select className="select filter-select" value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter by policy status"><option value="all">All statuses</option><option value="active">Active</option><option value="archived">Archived</option></select></div><div className="results-count">{sorted.length} policies</div></div>
    <div className="data-panel">{sorted.length ? <table className="data-table"><thead><tr><SortHeader label="Policy" column="name" sort={sort} onSort={toggleSort} /><th>Rule</th><SortHeader label="Priority" column="priority" sort={sort} onSort={toggleSort} /><SortHeader label="Effective" column="effective" sort={sort} onSort={toggleSort} /><SortHeader label="Impact" column="impact" sort={sort} onSort={toggleSort} /><SortHeader label="Status" column="status" sort={sort} onSort={toggleSort} /></tr></thead><tbody>{sorted.map((policy) => {
      const version = policy.versions.at(-1); const impact = impacts[policy.id]; const firstCondition = version?.condition_group.conditions[0];
      return <tr key={policy.id}><td><Link href={`/policies/${policy.id}`}><span className="primary-cell">{policy.name}</span><span className="secondary-cell">Version {version?.version_number ?? "—"}</span></Link></td><td>{firstCondition ? <span>{firstCondition.field.replaceAll("_", " ")} {firstCondition.operator} <strong>{firstCondition.value}</strong></span> : "No current rule"}</td><td><span className="badge">P{version?.priority ?? "—"}</span></td><td>{formatDate(version?.effective_from)}</td><td><span className="primary-cell">{impact?.selected_employee_count ?? 0}</span><span className="secondary-cell">employees selected</span></td><td><span className={`badge ${policy.status === "active" ? "success" : ""}`}>{policy.status === "active" ? "Active" : "Archived"}</span></td></tr>;
    })}</tbody></table> : <div className="empty-state"><div className="empty-icon"><BookOpenCheck size={18} /></div><strong>No policies match</strong><span>Try another search or include archived policies.</span><button className="text-button" onClick={() => { setSearch(""); setStatus("all"); }}><X size={13} /> Clear filters</button></div>}<div className="pagination-footer"><span>Showing {sorted.length} of {policies.length}</span><span>Priority determines single-value winners</span></div></div>
  </>;
}

function SortHeader({ label, column, sort, onSort }: { label: string; column: "name" | "priority" | "effective" | "impact" | "status"; sort: { key: string; direction: "asc" | "desc" }; onSort(column: "name" | "priority" | "effective" | "impact" | "status"): void }) {
  const active = sort.key === column; const Icon = !active ? ArrowUpDown : sort.direction === "asc" ? ArrowUp : ArrowDown;
  return <th aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}><button className="sort-button" onClick={() => onSort(column)}>{label}<Icon size={11} /></button></th>;
}
