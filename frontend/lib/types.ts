export type Employee = {
  id: number;
  name: string;
  state: string;
  state_label: string;
  department: string;
  employee_type: string;
  location: string | null;
  start_date: string;
  manager_id: number | null;
};

export type EmployeeManagerSummary = {
  id: number;
  name: string;
};

export type EmployeeDetail = Employee & {
  manager: EmployeeManagerSummary | null;
};

export type EmployeeDirectoryItem = Employee & {
  active_assignment_count: number;
};

export type EmployeeManagerCandidate = {
  id: number;
  label: string;
};

export type EmployeeReferenceData = {
  departments: string[];
  employee_types: string[];
  states: StateOption[];
};

export type StateOption = {
  code: string;
  name: string;
  label: string;
  group: "states" | "territories" | "other";
};

export type CollectionPage<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type BackendStatus = {
  status: string;
  service: string;
  database: string;
};

export type AuditLogFacets = {
  entity_types: string[];
  actions: string[];
};

export type AssignmentField = {
  id: number;
  name: string;
  cardinality: "one" | "many";
  conflict_resolution: string;
  input: {
    type: "text" | "select";
    options: { value: string; label: string }[];
  };
};

export type AssignmentFieldOption = Omit<AssignmentField, "conflict_resolution">;

export type AssignmentFieldSummary = {
  id: number;
  name: string;
};

export type AssignmentConditionEvidence = {
  field?: string;
  operator?: string;
  expected: unknown;
  actual: unknown;
  expected_label?: string | null;
  actual_label?: string | null;
  result?: boolean | null;
};

export type AssignmentOrigin = {
  type?: string;
  group_id?: number | null;
  group_name?: string | null;
  matched_clauses?: {
    clause_id?: number | null;
    conditions?: AssignmentConditionEvidence[];
  }[];
};

export type AssignmentCandidate = {
  policy_id?: number | null;
  policy_name?: string | null;
  policy_version_id?: number | null;
  version_number?: number | null;
  value?: string | null;
  priority?: number | null;
  selected?: boolean;
  outcome?: string | null;
  origins?: AssignmentOrigin[];
};

export type AssignmentExplanation = {
  reason?: string;
  evaluation_date?: string | null;
  policy?: { id?: number | null; name?: string | null } | null;
  policy_version?: { id?: number | null; version_number?: number | null } | null;
  origins?: AssignmentOrigin[];
  selection?: {
    field?: string | null;
    field_id?: number | null;
    cardinality?: string | null;
    strategy?: string | null;
    source_selection?: string | null;
    priority?: number | null;
    candidates?: AssignmentCandidate[];
    replaced_policy_assignments?: {
      value?: string | null;
      source_policy_version_id?: number | null;
      policy_name?: string | null;
    }[];
  } | null;
  override?: { id?: number | null; value?: string | null } | null;
};

export type CurrentAssignment = {
  id: number;
  value: string;
  source_policy_version_id: number | null;
  source_override_id: number | null;
  explanation: AssignmentExplanation;
  assignment_field_definition: AssignmentFieldSummary;
};

export type AssignmentHistoryItem = {
  id: number;
  value: string;
  source_type: "policy" | "override";
  effective_from: string;
  effective_until: string | null;
  assignment_field_definition: AssignmentFieldSummary;
};

export type AssignmentPreview = {
  assignment_field_definition_id: number;
  assignment_field_name: string;
  value: string;
  source_type: "policy_version" | "override";
  source_id: number | null;
  source_is_proposed: boolean;
  explanation: Record<string, unknown>;
};

export type EmployeeAssignmentPreview = {
  type: "employee_create" | "employee_update";
  valid: boolean;
  before_assignments: AssignmentPreview[];
  after_assignments: AssignmentPreview[];
  conflicts: {
    code: string;
    message: string;
    path: (string | number)[];
    metadata: Record<string, unknown>;
  }[];
  warnings: string[];
};

export type PolicyAssignmentPreview = {
  type: "policy_create" | "policy_version_create";
  affected_employees: {
    employee_id: number;
    employee_name: string;
    department: string;
  }[];
  assignments_per_match: {
    assignment_field_definition_id: number;
    assignment_field_name: string;
    value: string;
  }[];
  conflict_message: string | null;
};

export type Condition = {
  field: string;
  operator: "=" | "<" | "<=" | ">" | ">=";
  value: string;
  display_value?: string;
};

export type ConditionGroup = {
  logical_operator: "and" | "or";
  conditions: Condition[];
  child_groups: ConditionGroup[];
};

export type PolicyVersion = {
  id: number;
  policy_id: number;
  version_number: number;
  priority: number;
  effective_from: string;
  effective_until: string | null;
  created_at: string;
  created_by: string | null;
  condition_group: ConditionGroup;
  values: { assignment_field_definition_id: number; value: string }[];
};

export type Policy = {
  id: number;
  name: string;
  status: "draft" | "active" | "archived";
  created_at: string;
  created_by: string | null;
  versions: PolicyVersion[];
  capabilities: {
    can_update: boolean;
    can_create_version: boolean;
    can_activate: boolean;
    can_archive: boolean;
  };
};

export type ConditionField = {
  id: number;
  key: string;
  label: string;
  description: string;
  field_type: "static" | "derived";
  data_type: string;
  allowed_operators: ("=" | "<" | "<=" | ">" | ">=")[];
  input: {
    type: "text" | "date" | "number" | "select" | "duration" | "resource";
    allows_null: boolean;
    placeholder: string | null;
    options: { value: string; label: string }[];
    reference_resource: string | null;
    minimum: number | null;
  };
};

export type PolicyImpact = {
  policy_id: number;
  matched_employee_count: number;
  selected_employee_count: number;
  selected_assignment_count: number;
  matched_without_selected_assignment_count: number;
  suppressed_by_override_employee_count: number;
  complete: boolean;
};

export type AssignmentSummary = {
  employee_count: number;
  employees_with_assignments: number;
  employees_without_assignments: number;
  assignment_count: number;
  policy_assignment_count: number;
  override_assignment_count: number;
  field_count: number;
  complete: boolean;
  conflicted_employee_count: number;
  fields: {
    assignment_field_definition: AssignmentField;
    assigned_employee_count: number;
    assignment_count: number;
  }[];
};

export type Group = { id: number; name: string };

export type GroupDirectoryItem = Group & {
  member_count: number;
  policy_count: number;
};

export type EmployeeOverride = {
  id: number;
  value: string;
  assignment_field_definition: AssignmentFieldSummary;
};

export type AuditLog = {
  id: number;
  actor: string;
  entity_type: string;
  entity_id: number;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  timestamp: string;
  entity_label: string;
};

export type CurrentUser = {
  id: number;
  email: string;
  name: string;
  status: "active" | "suspended" | "disabled";
  is_root: boolean;
  password_change_required: boolean;
  mfa_enabled: boolean;
  employee_id: number | null;
  employee_link_hidden: boolean;
  created_at: string;
  last_login_at: string | null;
  roles: RoleSummary[];
  permissions: string[];
};

export type RootSetupStatus = { setup_required: boolean };

export type Permission = {
  name: string;
  group: string;
  label: string;
  description: string;
};

export type RoleSummary = { id: number; name: string };

export type Role = RoleSummary & {
  description: string | null;
  employee_scope: "all" | "reporting_tree" | "self" | "none";
  assignment_field_scope: "all" | "selected" | "none";
  assignment_field_ids: number[];
  permissions: string[];
  user_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type RoleDirectoryItem = RoleSummary & {
  description: string | null;
  employee_scope: Role["employee_scope"];
  assignment_field_scope: Role["assignment_field_scope"];
  assignment_field_count: number;
  permission_count: number;
  permission_preview: string[];
  user_count: number;
};

export type RoleCandidate = RoleSummary & {
  employee_scope: Role["employee_scope"];
  assignment_field_scope: Role["assignment_field_scope"];
  assignment_field_count: number;
  permission_count: number;
  user_count: number;
};

export type EmployeeLinkSummary = {
  id: number;
  name: string;
  department: string;
};

export type EmployeeCandidate = EmployeeLinkSummary;

export type AssignmentFieldScopeOption = {
  id: number;
  name: string;
  cardinality: "one" | "many";
};

export type UserDirectoryItem = {
  id: number;
  email: string;
  name: string;
  status: User["status"];
  is_root: boolean;
  password_change_required: boolean;
  employee: EmployeeLinkSummary | null;
  employee_link_hidden: boolean;
  roles: RoleSummary[];
  effective_permission_count: number;
  has_all_permissions: boolean;
};

export type User = CurrentUser;

export type AccountSession = {
  id: number;
  current: boolean;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  created_ip: string | null;
  last_ip: string | null;
  user_agent: string | null;
  mfa_verified: boolean;
};

export type SecurityEvent = {
  id: number;
  event_type: string;
  severity: "info" | "warning" | "critical";
  details: Record<string, unknown>;
  created_at: string;
  acknowledged_at: string | null;
};

export type AccountSecurity = {
  mfa_enabled: boolean;
  mfa_required: boolean;
  sessions: AccountSession[];
  events: SecurityEvent[];
};

export type AccessReview = {
  generated_at: string;
  active_user_count: number;
  role_count: number;
  privileged_user_count: number;
  privileged_users_without_mfa: number;
  unused_role_count: number;
  findings: {
    severity: "info" | "warning" | "critical";
    code: string;
    subject_type: "user" | "role";
    subject_id: number;
    subject_name: string;
    message: string;
  }[];
};
