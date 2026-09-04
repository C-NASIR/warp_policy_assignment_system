export type Employee = {
  id: number;
  name: string;
  state: string;
  department: string;
  employee_type: string;
  location: string | null;
  start_date: string;
  manager_id: number | null;
};

export type AssignmentField = {
  id: number;
  name: string;
  cardinality: "one" | "many";
  conflict_resolution: string;
};

export type Assignment = {
  id: number;
  employee_id: number;
  assignment_field_definition_id: number;
  value: string;
  source_policy_version_id: number | null;
  source_override_id: number | null;
  explanation: Record<string, unknown>;
  effective_from: string;
  effective_until: string | null;
  assignment_field_definition: AssignmentField;
};

export type Condition = {
  field: string;
  operator: "=" | "<" | "<=" | ">" | ">=";
  value: string;
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
  status: "active" | "archived";
  created_at: string;
  versions: PolicyVersion[];
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
  fields: { assignment_field_definition: AssignmentField; assigned_employee_count: number; assignment_count: number }[];
};

export type Group = { id: number; name: string };

export type EmployeeOverride = {
  id: number;
  employee_id: number;
  assignment_field_definition_id: number;
  value: string;
  retired_at: string | null;
  assignment_field_definition: AssignmentField;
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
};

export type CurrentUser = {
  id: number;
  email: string;
  name: string;
  status: "active" | "suspended" | "disabled";
  is_root: boolean;
  password_change_required: boolean;
  employee_id: number | null;
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
  permissions: string[];
  user_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type User = CurrentUser;
