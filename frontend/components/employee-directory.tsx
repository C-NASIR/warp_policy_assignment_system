"use client";

import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown, Search, Users, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { PaginationControls } from "@/components/pagination-controls";
import { initials } from "@/lib/format";
import type { EmployeeDirectoryItem, EmployeeReferenceData } from "@/lib/types";

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
  filters: { search: string; department: string; employeeType: string };
}) {
  const router = useRouter();
  const [search, setSearch] = useState(filters.search);
  const [department, setDepartment] = useState(filters.department);
  const [type, setType] = useState(filters.employeeType);
  const [sort, setSort] = useState<{
    key: "name" | "department" | "location" | "employee_type";
    direction: "asc" | "desc";
  }>({ key: "name", direction: "asc" });
  const sorted = [...employees].sort((left, right) => {
    const leftValue = sort.key === "location" ? (left.location ?? left.state) : left[sort.key];
    const rightValue = sort.key === "location" ? (right.location ?? right.state) : right[sort.key];
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

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    const query = new URLSearchParams();
    if (search.trim()) query.set("search", search.trim());
    if (department) query.set("department", department);
    if (type) query.set("employee_type", type);
    router.push(query.size ? `/employees?${query}` : "/employees");
  }

  function resetFilters() {
    setSearch("");
    setDepartment("");
    setType("");
    router.push("/employees");
  }

  return (
    <>
      <form className="toolbar" onSubmit={applyFilters}>
        <div className="toolbar-left">
          <label className="search-box">
            <Search size={14} />
            <input
              className="input"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search employees"
              aria-label="Search employees"
            />
          </label>
          <select
            className="select filter-select"
            value={department}
            onChange={(event) => setDepartment(event.target.value)}
            aria-label="Filter by department"
          >
            <option value="">All departments</option>
            {referenceData.departments.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <select
            className="select filter-select"
            value={type}
            onChange={(event) => setType(event.target.value)}
            aria-label="Filter by employment type"
          >
            <option value="">All worker types</option>
            {referenceData.employee_types.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <button className="button secondary" type="submit">
            Apply
          </button>
        </div>
        <div className="results-count">{total} employees</div>
      </form>

      <div className="data-panel">
        {sorted.length ? (
          <table className="data-table">
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
                      <span className="primary-cell">{employee.name}</span>
                    </Link>
                  </td>
                  <td>{employee.department}</td>
                  <td>{employee.location ?? employee.state}</td>
                  <td>{employee.employee_type}</td>
                  <td>
                    <span className="badge accent">{employee.active_assignment_count} active</span>
                  </td>
                  <td>
                    <span className="badge success">
                      <span
                        className="system-dot"
                        style={{ boxShadow: "none", width: 5, height: 5 }}
                      />{" "}
                      Current
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
            department: filters.department,
            employee_type: filters.employeeType,
          }}
          total={total}
          limit={limit}
          offset={offset}
          itemLabel="employees"
        />
      </div>
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
