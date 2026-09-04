import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { assignmentFields, assignmentSummary, assignmentsByEmployee, auditLogs, conditionFields, employees, groupEmployeeIds, groupPolicyIds, groups, overridesByEmployee, policies, policyImpacts } from "./demo-data";
import type { Assignment, AssignmentField, AssignmentSummary, AuditLog, ConditionField, CurrentUser, Employee, EmployeeOverride, Group, Permission, Policy, PolicyImpact, Role, RootSetupStatus, User } from "./types";

const configuredApiUrl = process.env.POLICY_API_URL?.replace(/\/$/, "");
const sessionCookieName = "policyos_session";

export const apiConfigured = Boolean(configuredApiUrl);

async function sessionHeaders(): Promise<Record<string, string>> {
  const token = (await cookies()).get(sessionCookieName)?.value;
  return token ? { Cookie: `${sessionCookieName}=${token}` } : {};
}

async function read<T>(path: string, fallback: T): Promise<T> {
  if (!configuredApiUrl) return fallback;
  const response = await fetch(`${configuredApiUrl}${path}`, {
    headers: { ...(await sessionHeaders()), Accept: "application/json" },
    cache: "no-store",
  });
  if (response.status === 401) redirect("/login");
  if (response.status === 403) {
    const user = await getCurrentUser();
    redirect(user?.password_change_required ? "/account/security" : "/forbidden");
  }
  if (response.status === 404) return fallback;
  if (!response.ok) throw new Error(`Policy API request failed with ${response.status}`);
  return response.json() as Promise<T>;
}

export async function getRootSetupStatus(): Promise<RootSetupStatus> {
  if (!configuredApiUrl) return { setup_required: false };
  const response = await fetch(`${configuredApiUrl}/auth/setup-status`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Policy API setup request failed with ${response.status}`);
  return response.json() as Promise<RootSetupStatus>;
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  if (!configuredApiUrl) return null;
  const headers = await sessionHeaders();
  if (!headers.Cookie) return null;
  const response = await fetch(`${configuredApiUrl}/auth/me`, {
    headers: { ...headers, Accept: "application/json" },
    cache: "no-store",
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(`Policy API session request failed with ${response.status}`);
  return response.json() as Promise<CurrentUser>;
}

export const getEmployees = () => read<Employee[]>("/employees?limit=500", employees);
export const getPolicies = () => read<Policy[]>("/policies?limit=500", policies);
export const getAssignmentFields = () => read<AssignmentField[]>("/assignment-fields?limit=500", assignmentFields);
export const getConditionFields = () => read<ConditionField[]>("/condition-fields?limit=500", conditionFields);
export const getAssignmentSummary = () => read<AssignmentSummary>("/assignment-summary", assignmentSummary);
export const getGroups = () => read<Group[]>("/groups?limit=500", groups);
export const getAuditLogs = () => read<AuditLog[]>("/audit-logs?limit=100", auditLogs);
export const getPermissions = () => read<Permission[]>("/authorization/permissions?limit=500", []);
export const getAuthorizationAssignmentFields = () => read<AssignmentField[]>("/authorization/assignment-fields", assignmentFields);
export const getRoles = () => read<Role[]>("/roles?limit=500", []);
export const getUsers = () => read<User[]>("/users?limit=500", []);

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
