"use client";

import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown, BookOpenCheck, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { type SubmitEvent, useState } from "react";
import { PaginationControls } from "@/components/shared";
import { Badge, Button, DataTable, Panel, TextInput } from "@/components/ui";
import { formatDate } from "@/lib/format";
import type { Policy, PolicyImpact } from "@/lib/types";

export function PolicyDirectory({
  policies,
  impacts,
  total,
  limit,
  offset,
  filters,
}: {
  policies: Policy[];
  impacts: Record<number, PolicyImpact | null>;
  total: number;
  limit: number;
  offset: number;
  filters: { search: string; status: string };
}) {
  const router = useRouter();
  const [search, setSearch] = useState(filters.search);
  const [status, setStatus] = useState(filters.status);
  const [sort, setSort] = useState<{
    key: "name" | "priority" | "effective" | "impact" | "status";
    direction: "asc" | "desc";
  }>({ key: "name", direction: "asc" });
  const sorted = [...policies].sort((left, right) => {
    const leftVersion = left.versions.at(-1);
    const rightVersion = right.versions.at(-1);
    const values = {
      name: [left.name, right.name],
      priority: [leftVersion?.priority ?? 0, rightVersion?.priority ?? 0],
      effective: [leftVersion?.effective_from ?? "", rightVersion?.effective_from ?? ""],
      impact: [
        impacts[left.id]?.selected_employee_count ?? 0,
        impacts[right.id]?.selected_employee_count ?? 0,
      ],
      status: [left.status, right.status],
    }[sort.key];
    const result =
      typeof values[0] === "number"
        ? Number(values[0]) - Number(values[1])
        : String(values[0]).localeCompare(String(values[1]));
    return result * (sort.direction === "asc" ? 1 : -1);
  });
  function toggleSort(key: typeof sort.key) {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" },
    );
  }
  function applyFilters(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = new URLSearchParams();
    if (search.trim()) query.set("search", search.trim());
    if (status) query.set("status", status);
    router.push(query.size ? `/policies?${query}` : "/policies");
  }
  function resetFilters() {
    setSearch("");
    setStatus("all");
    router.push("/policies?status=all");
  }

  function selectStatus(nextStatus: string) {
    setStatus(nextStatus);
    const query = new URLSearchParams();
    if (search.trim()) query.set("search", search.trim());
    query.set("status", nextStatus);
    router.push(`/policies?${query}`);
  }

  function clearSearch() {
    setSearch("");
    router.push(`/policies?status=${status}`);
  }
  return (
    <>
      <section className="directory-controls" aria-label="Policy directory controls">
        <div className="directory-controls-head">
          <div>
            <span className="section-kicker">Policy library</span>
            <strong>{total} policies in this view</strong>
          </div>
          <div className="filter-tabs" role="group" aria-label="Filter policies by status">
            {[
              ["active", "Active"],
              ["draft", "Draft"],
              ["archived", "Archived"],
              ["all", "All"],
            ].map(([value, label]) => (
              <button
                className={status === value ? "active" : undefined}
                type="button"
                key={value}
                onClick={() => selectStatus(value)}
                aria-pressed={status === value}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <form className="toolbar" onSubmit={applyFilters}>
          <div className="toolbar-left">
            <label className="search-box">
              <Search size={14} />
              <TextInput
                className="input"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search policies"
                aria-label="Search policies"
              />
            </label>
            <Button variant="secondary" type="submit">
              Search
            </Button>
          </div>
          <span className="results-count">Sorted by {sort.key}</span>
        </form>
        {filters.search && (
          <div className="active-filter-row" aria-label="Applied filters">
            <span>Applied</span>
            <button
              className="filter-chip"
              type="button"
              onClick={clearSearch}
              aria-label={`Remove search filter ${filters.search}`}
            >
              Search: {filters.search} <X size={11} aria-hidden="true" />
            </button>
            <button className="clear-filters" type="button" onClick={resetFilters}>
              Reset view
            </button>
          </div>
        )}
      </section>
      <Panel as="div" clipped>
        {sorted.length ? (
          <DataTable>
            <thead>
              <tr>
                <SortHeader label="Policy" column="name" sort={sort} onSort={toggleSort} />
                <th>Rule</th>
                <SortHeader label="Priority" column="priority" sort={sort} onSort={toggleSort} />
                <SortHeader label="Effective" column="effective" sort={sort} onSort={toggleSort} />
                <SortHeader label="Impact" column="impact" sort={sort} onSort={toggleSort} />
                <SortHeader label="Status" column="status" sort={sort} onSort={toggleSort} />
              </tr>
            </thead>
            <tbody>
              {sorted.map((policy) => {
                const version = policy.versions.at(-1);
                const impact = impacts[policy.id];
                const firstCondition = version?.condition_group.conditions[0];
                return (
                  <tr key={policy.id}>
                    <td>
                      <Link href={`/policies/${policy.id}`}>
                        <span className="primary-cell">{policy.name}</span>
                        <span className="secondary-cell">
                          Version {version?.version_number ?? "—"}
                        </span>
                      </Link>
                    </td>
                    <td>
                      {firstCondition ? (
                        <span>
                          {firstCondition.field.replaceAll("_", " ")} {firstCondition.operator}{" "}
                          <strong>{firstCondition.display_value ?? firstCondition.value}</strong>
                        </span>
                      ) : (
                        "No current rule"
                      )}
                    </td>
                    <td>
                      <Badge>P{version?.priority ?? "—"}</Badge>
                    </td>
                    <td>{formatDate(version?.effective_from)}</td>
                    <td>
                      <span className="primary-cell">{impact?.selected_employee_count ?? 0}</span>
                      <span className="secondary-cell">employees selected</span>
                    </td>
                    <td>
                      <Badge
                        tone={
                          policy.status === "active"
                            ? "success"
                            : policy.status === "draft"
                              ? "accent"
                              : "neutral"
                        }
                      >
                        {policy.status === "active"
                          ? "Active"
                          : policy.status === "draft"
                            ? "Draft"
                            : "Archived"}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </DataTable>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">
              <BookOpenCheck size={18} />
            </div>
            <strong>No policies match</strong>
            <span>Try another search or include archived policies.</span>
            <button className="text-button" onClick={resetFilters}>
              <X size={13} /> Clear filters
            </button>
          </div>
        )}
        <PaginationControls
          path="/policies"
          params={{ search: filters.search, status: filters.status }}
          total={total}
          limit={limit}
          offset={offset}
          itemLabel="policies"
        />
      </Panel>
    </>
  );
}

function SortHeader({
  label,
  column,
  sort,
  onSort,
}: {
  label: string;
  column: "name" | "priority" | "effective" | "impact" | "status";
  sort: { key: string; direction: "asc" | "desc" };
  onSort(column: "name" | "priority" | "effective" | "impact" | "status"): void;
}) {
  const active = sort.key === column;
  const Icon = !active ? ArrowUpDown : sort.direction === "asc" ? ArrowUp : ArrowDown;
  return (
    <th aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}>
      <button className="sort-button" onClick={() => onSort(column)}>
        {label}
        <Icon size={11} />
      </button>
    </th>
  );
}
