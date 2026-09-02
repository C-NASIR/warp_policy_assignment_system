import { assignmentFields, assignmentSummary, assignmentsByEmployee, auditLogs, conditionFields, employees, groupEmployeeIds, groupPolicyIds, groups, overridesByEmployee, policies, policyImpacts } from "./demo-data";
import type { Assignment, AssignmentField, AssignmentSummary, AuditLog, ConditionField, Employee, EmployeeOverride, Group, Policy, PolicyImpact } from "./types";

const apiUrl = process.env.POLICY_API_URL ?? "http://127.0.0.1:8000";
const apiToken = process.env.POLICY_API_TOKEN;

export const apiConfigured = Boolean(apiToken);

async function read<T>(path: string, fallback: T): Promise<T> {
  if (!apiToken) return fallback;
  const response = await fetch(`${apiUrl}${path}`, {
    headers: { Authorization: `Bearer ${apiToken}`, Accept: "application/json" },
    cache: "no-store",
  });
  if (response.status === 404) return fallback;
  if (!response.ok) throw new Error(`Policy API request failed with ${response.status}`);
  return response.json() as Promise<T>;
}

export const getEmployees = () => read<Employee[]>("/employees?limit=500", employees);
export const getPolicies = () => read<Policy[]>("/policies?limit=500", policies);
export const getAssignmentFields = () => read<AssignmentField[]>("/assignment-fields?limit=500", assignmentFields);
export const getConditionFields = () => read<ConditionField[]>("/condition-fields?limit=500", conditionFields);
export const getAssignmentSummary = () => read<AssignmentSummary>("/assignment-summary", assignmentSummary);
export const getGroups = () => read<Group[]>("/groups?limit=500", groups);
export const getAuditLogs = () => read<AuditLog[]>("/audit-logs?limit=100", auditLogs);

export async function getEmployee(id: number) {
  return read<Employee | null>(`/employees/${id}`, employees.find((item) => item.id === id) ?? null);
}

export async function getEmployeeAssignments(id: number) {
  return read<Assignment[]>(`/employees/${id}/assignments?limit=500`, assignmentsByEmployee[id] ?? []);
}

export async function getPolicy(id: number) {
  return read<Policy | null>(`/policies/${id}`, policies.find((item) => item.id === id) ?? null);
}

export async function getPolicyImpact(id: number) {
  return read<PolicyImpact | null>(`/policies/${id}/impact-summary`, policyImpacts[id] ?? null);
}

export async function getGroup(id: number) {
  return read<Group | null>(`/groups/${id}`, groups.find((item) => item.id === id) ?? null);
}

export async function getGroupEmployees(id: number) {
  return read<Employee[]>(`/groups/${id}/employees?limit=500`, employees.filter((item) => groupEmployeeIds[id]?.includes(item.id)));
}

export async function getGroupPolicies(id: number) {
  return read<Policy[]>(`/groups/${id}/policies?limit=500`, policies.filter((item) => groupPolicyIds[id]?.includes(item.id)));
}

export async function getEmployeeOverrides(id: number) {
  return read<EmployeeOverride[]>(`/employees/${id}/overrides?limit=500`, overridesByEmployee[id] ?? []);
}

export async function getEmployeeAssignmentHistory(id: number) {
  return read<Assignment[]>(`/employees/${id}/assignments/history?limit=500`, assignmentsByEmployee[id] ?? []);
}
