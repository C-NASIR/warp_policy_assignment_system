"use client";

import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown, Search, Users, X } from "lucide-react";
import { type SubmitEvent, useState } from "react";
import {
  AppliedFilterRow,
  DirectoryResultsStatus,
  PaginationControls,
  StateCombobox,
  useFilterNavigation,
} from "@/components/shared";
import { Badge, Button, DataTable, Panel, SelectInput, TextInput } from "@/components/ui";
import { formatEmployeeId, initials } from "@/lib/format";
import type { EmployeeDirectoryItem, EmployeeReferenceData } from "@/lib/types";
import styles from "./employee-directory.module.css";

export function EmployeeDirectory({
  employees,
  referenceData,
  total,
  limit,
  offset,
  filters,
}: {
  employees: EmployeeDirectoryItem[];
  referenceData: EmployeeReferenceData;
  total: number;
  limit: number;
  offset: number;
  filters: { search: string; state: string; department: string; employeeType: string };
}) {
  const navigation = useFilterNavigation(filters);
  const [search, setSearch] = useState(filters.search);
  const [state, setState] = useState(filters.state);
  const [department, setDepartment] = useState(filters.department);
  const [type, setType] = useState(filters.employeeType);
  const [sort, setSort] = useState<{
    key: "name" | "department" | "location" | "employee_type";
    direction: "asc" | "desc";
  }>({ key: "name", direction: "asc" });
  const applied = navigation.filters;
  const activeFilters = [
    applied.search ? { key: "search", label: `Search: ${applied.search}` } : null,
    applied.state ? { key: "state", label: `State: ${applied.state}` } : null,
    applied.department ? { key: "department", label: applied.department } : null,
    applied.employeeType ? { key: "employee_type", label: applied.employeeType } : null,
  ].filter((item): item is { key: string; label: string } => Boolean(item));

  const sorted = [...employees].sort((left, right) => {
    const leftValue =
      sort.key === "location" ? (left.location ?? left.state_label) : left[sort.key];
    const rightValue =
      sort.key === "location" ? (right.location ?? right.state_label) : right[sort.key];
    return (
      String(leftValue).localeCompare(String(rightValue)) * (sort.direction === "asc" ? 1 : -1)
    );
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
    if (state) query.set("state", state);
    if (department) query.set("department", department);
    if (type) query.set("employee_type", type);
    navigation.navigate(query.size ? `/employees?${query}` : "/employees", {
      search: search.trim(),
      state,
      department,
      employeeType: type,
    });
  }

  function resetFilters() {
    setSearch("");
    setState("");
    setDepartment("");
    setType("");
    navigation.navigate("/employees", {
      search: "",
      state: "",
      department: "",
      employeeType: "",
    });
  }

  function removeFilter(key: string) {
    const query = new URLSearchParams();
    if (applied.search && key !== "search") query.set("search", applied.search);
    if (applied.state && key !== "state") query.set("state", applied.state);
    if (applied.department && key !== "department") query.set("department", applied.department);
    if (applied.employeeType && key !== "employee_type")
      query.set("employee_type", applied.employeeType);
    if (key === "search") setSearch("");
    if (key === "state") setState("");
    if (key === "department") setDepartment("");
    if (key === "employee_type") setType("");
    navigation.navigate(query.size ? `/employees?${query}` : "/employees", {
      search: key === "search" ? "" : applied.search,
      state: key === "state" ? "" : applied.state,
      department: key === "department" ? "" : applied.department,
      employeeType: key === "employee_type" ? "" : applied.employeeType,
    });
  }

  return (
    <>
      <section className="directory-controls" aria-label="Employee directory controls">
        <div className="directory-controls-head">
          <div>
            <span className="section-kicker">Directory</span>
            <strong>{total} employees</strong>
          </div>
          <DirectoryResultsStatus pending={navigation.isPending}>
            {activeFilters.length
              ? `${activeFilters.length} active ${activeFilters.length === 1 ? "filter" : "filters"}`
              : "Showing all employees"}
          </DirectoryResultsStatus>
        </div>
        <form className="toolbar" onSubmit={applyFilters}>
          <div className="toolbar-left">
            <label className="search-box">
              <Search size={14} />
              <TextInput
                className="input"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search employees"
                aria-label="Search employees"
              />
            </label>
            <StateCombobox
              states={referenceData.states}
              value={state}
              required={false}
              placeholder="All states/jurisdictions"
              ariaLabel="Filter by state or jurisdiction"
              onChange={setState}
            />
            <SelectInput
              className="filter-select"
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
              aria-label="Filter by department"
            >
              <option value="">All departments</option>
              {referenceData.departments.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </SelectInput>
            <SelectInput
              className="filter-select"
              value={type}
              onChange={(event) => setType(event.target.value)}
              aria-label="Filter by employment type"
            >
              <option value="">All worker types</option>
              {referenceData.employee_types.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </SelectInput>
            <Button variant="secondary" type="submit">
              Apply filters
            </Button>
          </div>
        </form>
        <AppliedFilterRow filters={activeFilters} onRemove={removeFilter} onClear={resetFilters} />
      </section>

      <Panel as="div" className="results-region" clipped aria-busy={navigation.isPending}>
        {sorted.length ? (
          <DataTable>
            <thead>
              <tr>
                <SortHeader label="Employee" column="name" sort={sort} onSort={toggleSort} />
                <SortHeader
                  label="Department"
                  column="department"
                  sort={sort}
                  onSort={toggleSort}
                />
                <SortHeader label="Location" column="location" sort={sort} onSort={toggleSort} />
                <SortHeader
                  label="Worker type"
                  column="employee_type"
                  sort={sort}
                  onSort={toggleSort}
                />
                <th>Assignments</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((employee) => (
                <tr key={employee.id}>
                  <td>
                    <Link className="person-cell" href={`/employees/${employee.id}`}>
                      <span className="avatar">{initials(employee.name)}</span>
                      <span className="employee-identity">
                        <span className="primary-cell">{employee.name}</span>
                        <span className="secondary-cell">
                          Employee {formatEmployeeId(employee.id)}
                        </span>
                      </span>
                    </Link>
                  </td>
                  <td>{employee.department}</td>
                  <td>{employee.location ?? employee.state_label}</td>
                  <td>{employee.employee_type}</td>
                  <td>
                    <Badge tone="accent">{employee.active_assignment_count} active</Badge>
                  </td>
                  <td>
                    <Badge tone="success">
                      <span className={`system-dot ${styles.currentDot}`} /> Current
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">
              <Users size={18} />
            </div>
            <strong>No employees match</strong>
            <span>Try a different search or clear the current filters.</span>
            <button className="text-button" onClick={resetFilters}>
              <X size={13} /> Clear filters
            </button>
          </div>
        )}
        <PaginationControls
          path="/employees"
          params={{
            search: filters.search,
            state: filters.state,
            department: filters.department,
            employee_type: filters.employeeType,
          }}
          total={total}
          limit={limit}
          offset={offset}
          itemLabel="employees"
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
  column: "name" | "department" | "location" | "employee_type";
  sort: { key: string; direction: "asc" | "desc" };
  onSort(column: "name" | "department" | "location" | "employee_type"): void;
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
