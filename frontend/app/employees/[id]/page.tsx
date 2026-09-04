import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight, Info, Pencil, ShieldCheck } from "lucide-react";
import { notFound } from "next/navigation";
import { AssignmentCard } from "@/components/assignment-card";
import { EmployeeEditor } from "@/components/employee-form";
import { OverrideManager } from "@/components/override-manager";
import { apiConfigured, getAssignmentFields, getCurrentUser, getEmployee, getEmployeeAssignmentHistory, getEmployeeAssignments, getEmployeeOverrides, getEmployees } from "@/lib/backend";
import { formatDate, initials } from "@/lib/format";
import { hasPermission } from "@/lib/permissions";

export async function generateMetadata({ params }: PageProps<"/employees/[id]">): Promise<Metadata> {
  const { id } = await params; const employee = await getEmployee(Number(id));
  return { title: employee?.name ?? "Employee", description: employee ? `Policy assignments for ${employee.name}` : "Employee details", openGraph: { images: [] }, twitter: { images: [] } };
}

export default async function EmployeeDetailPage({ params }: PageProps<"/employees/[id]">) {
  const { id } = await params;
  const user = await getCurrentUser();
  const canReadAssignments = !apiConfigured || hasPermission(user, "assignments:read");
  const canReadSettings = !apiConfigured || hasPermission(user, "settings:read");
  const [employee, assignments, allEmployees, fields, overrides, history] = await Promise.all([
    getEmployee(Number(id)),
    canReadAssignments ? getEmployeeAssignments(Number(id)) : [],
    getEmployees(),
    canReadSettings ? getAssignmentFields() : [],
    canReadAssignments ? getEmployeeOverrides(Number(id)) : [],
    canReadAssignments ? getEmployeeAssignmentHistory(Number(id)) : [],
  ]);
  if (!employee) notFound();
  const manager = allEmployees.find((item) => item.id === employee.manager_id);
  const policyCount = new Set(assignments.map((item) => item.source_policy_version_id).filter(Boolean)).size;
  const overrideCount = assignments.filter((item) => item.source_override_id).length;
  return (
    <>
      <div className="breadcrumb"><Link href="/employees">Employees</Link><ChevronRight size={11} /><span>{employee.name}</span></div>
      <div className="detail-hero">
        <div className="detail-identity"><div className="detail-avatar">{initials(employee.name)}</div><div><h1 className="detail-title">{employee.name}</h1><div className="detail-meta">{employee.department} · {employee.employee_type} · {employee.location ?? employee.state}</div></div></div>
        {hasPermission(user, "employees:update") && <EmployeeEditor employee={employee} employees={allEmployees} fields={fields} currentAssignments={assignments} apiConfigured={apiConfigured} trigger={<><Pencil size={14} /> Edit employee</>} compact />}
      </div>
      <div className={canReadAssignments ? "detail-grid" : "section-stack"}>
        <div className="section-stack">
          {canReadAssignments && <section className="panel"><div className="panel-header"><h2 className="panel-title">Current assignments</h2><span className="badge success">{assignments.length} resolved</span></div><div className="panel-body">
            {assignments.length ? <div className="assignment-list">{assignments.map((item) => <AssignmentCard assignment={item} key={item.id} />)}</div> : <div className="empty-state">No active assignments.</div>}
          </div></section>}
          <section className="panel"><div className="panel-header"><h2 className="panel-title">Employee profile</h2></div><div className="panel-body"><div className="profile-grid">
            <div><span className="label">Department</span><div className="profile-value">{employee.department}</div></div>
            <div><span className="label">Employment type</span><div className="profile-value">{employee.employee_type}</div></div>
            <div><span className="label">Work location</span><div className="profile-value">{employee.location ?? "Not set"}</div><div className="profile-caption">{employee.state}</div></div>
            <div><span className="label">Start date</span><div className="profile-value">{formatDate(employee.start_date)}</div></div>
            <div><span className="label">Manager</span><div className="profile-value">{manager?.name ?? "No manager"}</div></div>
            <div><span className="label">Employee ID</span><div className="profile-value">#{String(employee.id).padStart(4, "0")}</div></div>
          </div></div></section>
          {canReadAssignments && <OverrideManager employee={employee} fields={fields} initialOverrides={overrides} history={history} apiConfigured={apiConfigured} canManage={hasPermission(user, "assignments:manage")} />}
        </div>
        {canReadAssignments && <aside className="section-stack">
          <section className="panel"><div className="panel-header"><h2 className="panel-title">Assignment health</h2></div><div className="panel-body"><div className="side-stat"><div className="side-stat-value">{assignments.length}</div><div className="side-stat-label">Current assignment values</div></div><div className="side-stat"><div className="side-stat-value">{policyCount}</div><div className="side-stat-label">Source policies</div></div><div className="side-stat"><div className="side-stat-value">{overrideCount}</div><div className="side-stat-label">Manual overrides</div></div></div></section>
          <div className="callout"><Info size={15} /><span>Open any assignment to see the exact policy, matched facts, group origin, and priority decision.</span></div>
          {overrideCount > 0 && <div className="callout" style={{ background: "var(--warning-soft)", borderColor: "#eddaab", color: "#74501a" }}><ShieldCheck size={15} /><span>This employee has {overrideCount} manual override. Review it periodically to confirm it is still needed.</span></div>}
        </aside>}
      </div>
    </>
  );
}
