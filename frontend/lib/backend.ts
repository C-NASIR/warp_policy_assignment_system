import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type {
  AccessReview,
  AccountSecurity,
  AssignmentHistoryItem,
  AssignmentField,
  AssignmentFieldScopeOption,
  AssignmentSummary,
  AuditLog,
  AuditLogFacets,
  BackendStatus,
  CollectionPage,
  ConditionField,
  CurrentUser,
  CurrentAssignment,
  Employee,
  EmployeeDetail,
  EmployeeDirectoryItem,
  EmployeeReferenceData,
  EmployeeOverride,
  Group,
  GroupDirectoryItem,
  Permission,
  Policy,
  PolicyImpact,
  Role,
  RoleCandidate,
  RoleDirectoryItem,
  RootSetupStatus,
  UserDirectoryItem,
} from "./types";

const configuredApiUrl = process.env.POLICY_API_URL?.replace(/\/$/, "");
const sessionCookieName = "policyos_session";

function apiUrl(): string {
  if (!configuredApiUrl) {
    throw new Error("POLICY_API_URL is required to run the PolicyOS frontend.");
  }
  return configuredApiUrl;
}

async function sessionHeaders(): Promise<Record<string, string>> {
  const token = (await cookies()).get(sessionCookieName)?.value;
  return token ? { Cookie: `${sessionCookieName}=${token}` } : {};
}

async function backendResponse(path: string): Promise<Response> {
  const response = await fetch(`${apiUrl()}${path}`, {
    headers: { ...(await sessionHeaders()), Accept: "application/json" },
    cache: "no-store",
  });
  if (response.status === 401) redirect("/login");
  if (response.status === 403) {
    const user = await getCurrentUser();
    redirect(user?.password_change_required ? "/account/security" : "/forbidden");
  }
  if (!response.ok) throw new Error(`Policy API request failed with ${response.status}`);
  return response;
}

async function read<T>(path: string): Promise<T> {
  const response = await backendResponse(path);
  return response.json() as Promise<T>;
}

async function readOptional<T>(path: string): Promise<T | null> {
  const response = await fetch(`${apiUrl()}${path}`, {
    headers: { ...(await sessionHeaders()), Accept: "application/json" },
    cache: "no-store",
  });
  if (response.status === 401) redirect("/login");
  if (response.status === 403) {
    const user = await getCurrentUser();
    redirect(user?.password_change_required ? "/account/security" : "/forbidden");
  }
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Policy API request failed with ${response.status}`);
  return response.json() as Promise<T>;
}

async function readPage<T>(path: string): Promise<CollectionPage<T>> {
  const response = await backendResponse(path);
  const items = (await response.json()) as T[];
  return {
    items,
    total: Number(response.headers.get("x-total-count") ?? items.length),
    limit: Number(response.headers.get("x-limit") ?? items.length),
    offset: Number(response.headers.get("x-offset") ?? 0),
  };
}

async function readAll<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let offset = 0;
  while (true) {
    const separator = path.includes("?") ? "&" : "?";
    const page = await readPage<T>(`${path}${separator}limit=500&offset=${offset}`);
    items.push(...page.items);
    if (items.length >= page.total || page.items.length === 0) return items;
    offset += page.items.length;
  }
}

function collectionPath(path: string, values: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  return `${path}?${query}`;
}

export async function getRootSetupStatus(): Promise<RootSetupStatus> {
  const response = await fetch(`${apiUrl()}/auth/setup-status`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Policy API setup request failed with ${response.status}`);
  return response.json() as Promise<RootSetupStatus>;
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const baseUrl = apiUrl();
  const headers = await sessionHeaders();
  if (!headers.Cookie) return null;
  const response = await fetch(`${baseUrl}/auth/me`, {
    headers: { ...headers, Accept: "application/json" },
    cache: "no-store",
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(`Policy API session request failed with ${response.status}`);
  return response.json() as Promise<CurrentUser>;
}

export async function getBackendStatus(): Promise<BackendStatus> {
  const response = await fetch(`${apiUrl()}/`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Policy API readiness check failed with ${response.status}`);
  return response.json() as Promise<BackendStatus>;
}

export const getEmployees = () => readAll<EmployeeDirectoryItem>("/employees");
export const getEmployeePage = (options: {
  search?: string;
  state?: string;
  department?: string;
  employeeType?: string;
  limit: number;
  offset: number;
}) =>
  readPage<EmployeeDirectoryItem>(
    collectionPath("/employees", {
      search: options.search,
      state: options.state,
      department: options.department,
      employee_type: options.employeeType,
      limit: options.limit,
      offset: options.offset,
    }),
  );
export const getEmployeeReferenceData = () =>
  read<EmployeeReferenceData>("/employees/reference-data");
export const getPolicies = () => readAll<Policy>("/policies");
export const getPolicyPage = (options: {
  search?: string;
  status?: string;
  limit: number;
  offset: number;
}) =>
  readPage<Policy>(
    collectionPath("/policies", {
      search: options.search,
      status: options.status,
      limit: options.limit,
      offset: options.offset,
    }),
  );
export const getAssignmentFields = () => readAll<AssignmentField>("/assignment-fields");
export const getConditionFields = () => readAll<ConditionField>("/condition-fields");
export const getAssignmentSummary = () => read<AssignmentSummary>("/assignment-summary");
export const getGroups = () => readAll<Group>("/groups");
export const getGroupPage = (options: { search?: string; limit: number; offset: number }) =>
  readPage<GroupDirectoryItem>(
    collectionPath("/groups", {
      search: options.search,
      limit: options.limit,
      offset: options.offset,
    }),
  );
export const getAuditLogFacets = () => read<AuditLogFacets>("/audit-logs/facets");
export const getAuditLogPage = (options: {
  search?: string;
  entityType?: string;
  action?: string;
  limit: number;
  offset: number;
}) =>
  readPage<AuditLog>(
    collectionPath("/audit-logs", {
      search: options.search,
      entity_type: options.entityType,
      action: options.action,
      sort: "desc",
      limit: options.limit,
      offset: options.offset,
    }),
  );
export const getPermissions = () => readAll<Permission>("/authorization/permissions");
export const getAuthorizationAssignmentFields = () =>
  read<AssignmentFieldScopeOption[]>("/authorization/assignment-fields");
export const getRolePage = (options: { search?: string; limit: number; offset: number }) =>
  readPage<RoleDirectoryItem>(
    collectionPath("/roles", {
      search: options.search,
      limit: options.limit,
      offset: options.offset,
    }),
  );
export const getUserPage = (options: {
  search?: string;
  status?: string;
  roleId?: number;
  limit: number;
  offset: number;
}) =>
  readPage<UserDirectoryItem>(
    collectionPath("/users", {
      search: options.search,
      status: options.status,
      role_id: options.roleId,
      limit: options.limit,
      offset: options.offset,
    }),
  );
export const getRoleCandidate = async (id: number) => {
  const candidates = await read<RoleCandidate[]>(
    collectionPath("/authorization/role-candidates", { role_id: id, limit: 1 }),
  );
  return candidates[0] ?? null;
};
export const getRole = (id: number) => read<Role>(`/roles/${id}`);
export const getAccountSecurity = () => read<AccountSecurity>("/auth/security");
export const getAccessReview = () => read<AccessReview>("/authorization/access-review");
export async function getEmployee(id: number) {
  return readOptional<EmployeeDetail>(`/employees/${id}`);
}

export async function getEmployeeAssignments(id: number) {
  return readAll<CurrentAssignment>(`/employees/${id}/assignments`);
}

export async function getPolicy(id: number) {
  return readOptional<Policy>(`/policies/${id}`);
}

export async function getPolicyImpact(id: number) {
  return readOptional<PolicyImpact>(`/policies/${id}/impact-summary`);
}

export async function getGroup(id: number) {
  return readOptional<Group>(`/groups/${id}`);
}

export async function getGroupEmployees(id: number) {
  return readAll<Employee>(`/groups/${id}/employees`);
}

export async function getGroupPolicies(id: number) {
  return readAll<Policy>(`/groups/${id}/policies`);
}

export async function getEmployeeOverrides(id: number) {
  return readAll<EmployeeOverride>(`/employees/${id}/overrides`);
}

export async function getEmployeeAssignmentHistoryPage(
  id: number,
  options: { limit: number; offset: number; status: "inactive" | "all" },
) {
  return readPage<AssignmentHistoryItem>(
    collectionPath(`/employees/${id}/assignments/history`, options),
  );
}
