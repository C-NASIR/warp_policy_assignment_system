"use client";

import { ChevronDown, ChevronUp, Search, ScrollText } from "lucide-react";
import { useRouter } from "next/navigation";
import { type SubmitEvent, useState } from "react";
import { PaginationControls } from "@/components/shared";
import { Badge, Button, DataTable, Panel, SelectInput, TextInput } from "@/components/ui";
import { formatDate, titleCase } from "@/lib/format";
import type { AuditLog, AuditLogFacets } from "@/lib/types";

export function AuditLogExplorer({
  events,
  facets,
  total,
  limit,
  offset,
  filters,
}: {
  events: AuditLog[];
  facets: AuditLogFacets;
  total: number;
  limit: number;
  offset: number;
  filters: { search: string; entityType: string; action: string };
}) {
  const router = useRouter();
  const [search, setSearch] = useState(filters.search);
  const [entity, setEntity] = useState(filters.entityType);
  const [action, setAction] = useState(filters.action);
  const [expanded, setExpanded] = useState<number | null>(null);
  function applyFilters(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = new URLSearchParams();
    if (search.trim()) query.set("search", search.trim());
    if (entity) query.set("entity_type", entity);
    if (action) query.set("action", action);
    router.push(query.size ? `/audit?${query}` : "/audit");
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Accountability</p>
          <h1>Audit log</h1>
          <p className="page-subtitle">
            Trace who changed every policy, employee, group, assignment, and override.
          </p>
        </div>
        <Badge tone="accent">
          <ScrollText size={11} /> Append-only
        </Badge>
      </div>
      <form className="toolbar" onSubmit={applyFilters}>
        <div className="toolbar-left">
          <label className="search-box">
            <Search size={14} />
            <TextInput
              className="input"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search actor or change"
              aria-label="Search audit log"
            />
          </label>
          <SelectInput
            className="filter-select"
            value={entity}
            onChange={(event) => setEntity(event.target.value)}
            aria-label="Filter by entity"
          >
            <option value="">All entities</option>
            {facets.entity_types.map((item) => (
              <option key={item} value={item}>
                {titleCase(item)}
              </option>
            ))}
          </SelectInput>
          <SelectInput
            className="filter-select"
            value={action}
            onChange={(event) => setAction(event.target.value)}
            aria-label="Filter by action"
          >
            <option value="">All actions</option>
            {facets.actions.map((item) => (
              <option key={item} value={item}>
                {titleCase(item)}
              </option>
            ))}
          </SelectInput>
          <Button variant="secondary" type="submit">
            Apply
          </Button>
        </div>
        <span className="results-count">{total} events</span>
      </form>
      <Panel as="div" clipped>
        <div className="audit-table-scroll">
          <DataTable className="audit-table">
            <colgroup>
              <col className="audit-when-column" />
              <col className="audit-actor-column" />
              <col className="audit-entity-column" />
              <col className="audit-action-column" />
              <col />
              <col className="audit-details-column" />
            </colgroup>
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Entity</th>
                <th>Action</th>
                <th>Summary</th>
                <th aria-label="Details" />
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <AuditRow
                  event={event}
                  entityLabel={event.entity_label}
                  expanded={expanded === event.id}
                  onToggle={() =>
                    setExpanded((current) => (current === event.id ? null : event.id))
                  }
                  key={event.id}
                />
              ))}
            </tbody>
          </DataTable>
          {events.length === 0 && (
            <div className="empty-state compact">No audit events match those filters.</div>
          )}
        </div>
        <PaginationControls
          path="/audit"
          params={{
            search: filters.search,
            entity_type: filters.entityType,
            action: filters.action,
          }}
          total={total}
          limit={limit}
          offset={offset}
          itemLabel="events"
        />
      </Panel>
    </>
  );
}

function AuditRow({
  event,
  entityLabel,
  expanded,
  onToggle,
}: {
  event: AuditLog;
  entityLabel: string;
  expanded: boolean;
  onToggle(): void;
}) {
  const changedSnapshots = diffAuditSnapshots(event.before, event.after);

  return (
    <>
      <tr className="audit-event-row" onClick={onToggle}>
        <td>
          <time className="audit-time" dateTime={event.timestamp}>
            <span>{formatDate(event.timestamp)}</span>
            <small>{formatAuditTime(event.timestamp)}</small>
          </time>
        </td>
        <td>
          <span className="primary-cell audit-actor" title={event.actor}>
            {event.actor}
          </span>
        </td>
        <td>
          <span className="primary-cell">{entityLabel}</span>
          <span className="secondary-cell">{titleCase(event.entity_type)}</span>
        </td>
        <td>
          <Badge
            tone={
              event.action === "created"
                ? "success"
                : event.action === "deleted"
                  ? "warning"
                  : "accent"
            }
          >
            {titleCase(event.action)}
          </Badge>
        </td>
        <td>
          <span className="audit-summary">{summarizeChange(event.before, event.after)}</span>
        </td>
        <td>
          <button
            className="icon-button audit-expand-button"
            onClick={(clickEvent) => {
              clickEvent.stopPropagation();
              onToggle();
            }}
            aria-expanded={expanded}
            aria-label={expanded ? "Hide event payload" : "Show event payload"}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="audit-detail-row">
          <td colSpan={6}>
            <div className="audit-record-reference">
              Technical reference · {event.entity_type} #{event.entity_id}
            </div>
            <div className="audit-payload">
              <div className="audit-payload-before">
                <span className="label">Before</span>
                <pre>{formatAuditSnapshot(changedSnapshots.before)}</pre>
              </div>
              <div className="audit-payload-after">
                <span className="label">After</span>
                <pre>{formatAuditSnapshot(changedSnapshots.after)}</pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function diffAuditSnapshots(
  before: Record<string, unknown> | null,
  after: Record<string, unknown> | null,
) {
  if (!before || !after) return { before, after };
  return diffAuditRecords(before, after);
}

function diffAuditRecords(before: Record<string, unknown>, after: Record<string, unknown>) {
  const changedBefore: Record<string, unknown> = {};
  const changedAfter: Record<string, unknown> = {};
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);

  for (const key of keys) {
    const beforeHasKey = Object.hasOwn(before, key);
    const afterHasKey = Object.hasOwn(after, key);

    if (!beforeHasKey) {
      changedAfter[key] = after[key];
      continue;
    }
    if (!afterHasKey) {
      changedBefore[key] = before[key];
      continue;
    }

    const change = diffAuditValues(before[key], after[key]);
    if (!change) continue;
    changedBefore[key] = change.before;
    changedAfter[key] = change.after;
  }

  return { before: changedBefore, after: changedAfter };
}

function diffAuditValues(before: unknown, after: unknown) {
  if (auditValuesEqual(before, after)) return null;
  if (isAuditRecord(before) && isAuditRecord(after)) {
    return diffAuditRecords(before, after);
  }
  return { before, after };
}

function auditValuesEqual(before: unknown, after: unknown): boolean {
  if (Object.is(before, after)) return true;
  if (Array.isArray(before) && Array.isArray(after)) {
    return (
      before.length === after.length &&
      before.every((value, index) => auditValuesEqual(value, after[index]))
    );
  }
  if (isAuditRecord(before) && isAuditRecord(after)) {
    const beforeKeys = Object.keys(before);
    const afterKeys = Object.keys(after);
    return (
      beforeKeys.length === afterKeys.length &&
      beforeKeys.every(
        (key) => Object.hasOwn(after, key) && auditValuesEqual(before[key], after[key]),
      )
    );
  }
  return false;
}

function isAuditRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatAuditSnapshot(snapshot: Record<string, unknown> | null) {
  return snapshot === null ? "None" : JSON.stringify(snapshot, null, 2);
}

function summarizeChange(
  before: Record<string, unknown> | null,
  after: Record<string, unknown> | null,
) {
  if (!before && after)
    return meaningfulEntries(after)
      .slice(0, 2)
      .map(([key, value]) => `${formatAuditKey(key)}: ${formatAuditValue(value)}`)
      .join(" · ");
  if (before && after) {
    const key = meaningfulEntries(after).find(([item, value]) => before[item] !== value)?.[0];
    return key
      ? `${formatAuditKey(key)}: ${formatAuditValue(before[key])} → ${formatAuditValue(after[key])}`
      : "Metadata updated";
  }
  return "Record closed";
}

function meaningfulEntries(record: Record<string, unknown>) {
  const entries = Object.entries(record);
  const descriptive = entries.filter(
    ([key]) => key !== "id" && !key.endsWith("_id") && !key.endsWith("_at"),
  );
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
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(new Date(value));
}
