import type { Metadata } from "next";
import { AuditLogExplorer } from "@/components/audit-log-explorer";
import { apiConfigured, getAuditLogs, getCurrentUser, getEmployees, getGroups, getPolicies } from "@/lib/backend";
import { titleCase } from "@/lib/format";
import { hasPermission } from "@/lib/permissions";
import type { AuditLog, Employee, Group, Policy } from "@/lib/types";

export const metadata: Metadata = { title: "Audit log" };

export default async function AuditPage() {
  const user = await getCurrentUser();
  const [events, employees, policies, groups] = await Promise.all([
    getAuditLogs(),
    !apiConfigured || hasPermission(user, "employees:read") ? getEmployees() : [],
    !apiConfigured || hasPermission(user, "policies:read") ? getPolicies() : [],
    !apiConfigured || hasPermission(user, "groups:read") ? getGroups() : [],
  ]);
  const entityLabels = Object.fromEntries(events.map((event) => [event.id, auditEntityLabel(event, employees, policies, groups)]));
  return <AuditLogExplorer events={events} entityLabels={entityLabels} />;
}

function auditEntityLabel(event: AuditLog, employees: Employee[], policies: Policy[], groups: Group[]) {
  const snapshot = { ...(event.before ?? {}), ...(event.after ?? {}) };
  if (event.entity_type === "Employee") return employees.find((item) => item.id === event.entity_id)?.name ?? String(snapshot.name ?? "Employee");
  if (event.entity_type === "Policy") return policies.find((item) => item.id === event.entity_id)?.name ?? String(snapshot.name ?? "Policy");
  if (event.entity_type === "Group") return groups.find((item) => item.id === event.entity_id)?.name ?? String(snapshot.name ?? "Group");
  if (event.entity_type === "PolicyVersion") {
    if (typeof snapshot.name === "string") return snapshot.name;
    for (const policy of policies) {
      const version = policy.versions.find((item) => item.id === event.entity_id);
      if (version) return `${policy.name} · Version ${version.version_number}`;
    }
    return "Policy version";
  }
  const employeeId = typeof snapshot.employee_id === "number" ? snapshot.employee_id : null;
  const employee = employees.find((item) => item.id === employeeId);
  if (event.entity_type === "EmployeeAssignment") return employee ? `${employee.name} · Assignment` : "Employee assignment";
  if (event.entity_type === "EmployeeOverride") return employee ? `${employee.name} · Manual override` : "Manual override";
  if (event.entity_type === "EmployeeGroupMembership") return employee ? `${employee.name} · Group membership` : "Group membership";
  return titleCase(event.entity_type);
}
