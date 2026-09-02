"use client";

import Link from "next/link";
import { Search, Users } from "lucide-react";
import { useState } from "react";
import { initials } from "@/lib/format";
import type { Employee } from "@/lib/types";

export function EmployeeDirectory({ employees }: { employees: Employee[] }) {
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("all");
  const [type, setType] = useState("all");
  const departments = [...new Set(employees.map((item) => item.department))].sort();
  const types = [...new Set(employees.map((item) => item.employee_type))].sort();
  const filtered = employees.filter((employee) => {
    const haystack = `${employee.name} ${employee.department} ${employee.location} ${employee.state}`.toLowerCase();
    return haystack.includes(search.toLowerCase()) && (department === "all" || employee.department === department) && (type === "all" || employee.employee_type === type);
  });

  return (
    <>
      <div className="toolbar">
        <div className="toolbar-left">
          <label className="search-box">
            <Search size={14} />
            <input className="input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search employees" aria-label="Search employees" />
          </label>
          <select className="select filter-select" value={department} onChange={(event) => setDepartment(event.target.value)} aria-label="Filter by department">
            <option value="all">All departments</option>{departments.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select className="select filter-select" value={type} onChange={(event) => setType(event.target.value)} aria-label="Filter by employment type">
            <option value="all">All worker types</option>{types.map((item) => <option key={item}>{item}</option>)}
          </select>
        </div>
        <div className="results-count">{filtered.length} employees</div>
      </div>

      <div className="data-panel">
        {filtered.length ? (
          <table className="data-table">
            <thead><tr><th>Employee</th><th>Department</th><th>Location</th><th>Worker type</th><th>Assignments</th><th>Status</th></tr></thead>
            <tbody>{filtered.map((employee) => (
              <tr key={employee.id}>
                <td><Link className="person-cell" href={`/employees/${employee.id}`}><span className="avatar">{initials(employee.name)}</span><span><span className="primary-cell">{employee.name}</span><span className="secondary-cell">Employee #{String(employee.id).padStart(4, "0")}</span></span></Link></td>
                <td>{employee.department}</td><td>{employee.location ?? employee.state}</td><td>{employee.employee_type}</td>
                <td><span className="badge accent">{employee.id === 1 ? 6 : 3 + (employee.id % 3)} active</span></td>
                <td><span className="badge success"><span className="system-dot" style={{ boxShadow: "none", width: 5, height: 5 }} /> Current</span></td>
              </tr>
            ))}</tbody>
          </table>
        ) : <div className="empty-state"><div className="empty-icon"><Users size={18} /></div>No employees match those filters.</div>}
        <div className="pagination-footer"><span>Showing {filtered.length} of {employees.length}</span><span>Updated just now</span></div>
      </div>
    </>
  );
}
