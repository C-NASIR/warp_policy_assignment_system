import type { Assignment, AssignmentField, AssignmentSummary, AuditLog, ConditionField, Employee, EmployeeOverride, Group, Policy, PolicyImpact } from "./types";

export const employees: Employee[] = [
  { id: 1, name: "Alice Johnson", state: "California", department: "Engineering", employee_type: "Full-time", location: "San Francisco", start_date: "2021-04-12", manager_id: 4 },
  { id: 2, name: "Jordan Lee", state: "New York", department: "Product", employee_type: "Full-time", location: "New York", start_date: "2023-08-21", manager_id: 5 },
  { id: 3, name: "Devon Moore", state: "Texas", department: "Sales", employee_type: "Contractor", location: "Austin", start_date: "2025-01-06", manager_id: 6 },
  { id: 4, name: "Maya Patel", state: "California", department: "Engineering", employee_type: "Full-time", location: "San Francisco", start_date: "2018-06-18", manager_id: null },
  { id: 5, name: "Priya Shah", state: "Illinois", department: "Product", employee_type: "Full-time", location: "Chicago", start_date: "2019-11-04", manager_id: null },
  { id: 6, name: "Mateo Garcia", state: "Florida", department: "Sales", employee_type: "Full-time", location: "Remote", start_date: "2022-02-14", manager_id: null },
  { id: 7, name: "Samira Okafor", state: "Washington", department: "Design", employee_type: "Full-time", location: "Seattle", start_date: "2024-03-11", manager_id: 5 },
  { id: 8, name: "Theo Martin", state: "California", department: "Support", employee_type: "Part-time", location: "Los Angeles", start_date: "2025-10-20", manager_id: 6 },
];

export const assignmentFields: AssignmentField[] = [
  { id: 1, name: "Pay schedule", cardinality: "one", conflict_resolution: "priority" },
  { id: 2, name: "Vacation policy", cardinality: "one", conflict_resolution: "priority" },
  { id: 3, name: "Application access", cardinality: "many", conflict_resolution: "priority" },
  { id: 4, name: "Compliance training", cardinality: "many", conflict_resolution: "priority" },
  { id: 5, name: "Equipment stipend", cardinality: "one", conflict_resolution: "priority" },
];

export const conditionFields: ConditionField[] = [
  field(1, "state", "State", "The employee’s state or region of employment.", "text", ["="]),
  field(2, "department", "Department", "The employee’s current department.", "text", ["="]),
  field(3, "employee_type", "Employee type", "The employee’s employment classification.", "text", ["="]),
  field(4, "location", "Location", "The employee’s current work location.", "text", ["="]),
  field(5, "start_date", "Start date", "The employee’s original start date.", "date", ["=", "<", "<=", ">", ">="]),
  field(6, "tenure", "Tenure", "Completed whole calendar years of tenure.", "duration", ["=", "<", "<=", ">", ">="]),
  field(7, "is_manager", "Is manager", "Whether the employee has direct reports.", "select", ["="], [{ value: "true", label: "True" }, { value: "false", label: "False" }]),
  field(8, "direct_report_count", "Direct report count", "The employee’s number of direct reports.", "number", ["=", "<", "<=", ">", ">="]),
  field(9, "reports_under", "Reports under", "Whether the employee reports beneath a selected manager.", "resource", ["="]),
  field(10, "management_level", "Management level", "Reporting hops from the top of the org chart.", "number", ["=", "<", "<=", ">", ">="]),
];

function field(
  id: number,
  key: string,
  label: string,
  description: string,
  inputType: ConditionField["input"]["type"],
  operators: ConditionField["allowed_operators"],
  options: { value: string; label: string }[] = [],
): ConditionField {
  return {
    id, key, label, description, field_type: ["tenure", "is_manager", "direct_report_count", "reports_under", "management_level"].includes(key) ? "derived" : "static",
    data_type: inputType, allowed_operators: operators,
    input: { type: inputType, allows_null: false, placeholder: inputType === "duration" ? "2 years" : null, options, reference_resource: inputType === "resource" ? "employees" : null, minimum: inputType === "number" ? 0 : null },
  };
}

const now = "2026-09-02T14:30:00Z";

export const assignmentsByEmployee: Record<number, Assignment[]> = {
  1: [
    assignment(101, 1, assignmentFields[0], "Bi-weekly", 11, explanation("California Pay Schedule", 11, 20, "State", "California")),
    assignment(102, 1, assignmentFields[1], "Flexible PTO", 15, explanation("Senior Employee PTO", 15, 15, "Tenure", "P5Y")),
    assignment(103, 1, assignmentFields[2], "GitHub", 12, groupExplanation("Engineering Access", 12, "Engineering")),
    assignment(104, 1, assignmentFields[2], "Linear", 12, groupExplanation("Engineering Access", 12, "Engineering")),
    assignment(105, 1, assignmentFields[3], "CA Workplace Harassment", 13, explanation("California Compliance", 13, 30, "State", "California")),
    assignment(106, 1, assignmentFields[4], "$1,000 annual", 14, explanation("Engineering Equipment", 14, 10, "Department", "Engineering")),
  ],
  2: [
    assignment(201, 2, assignmentFields[0], "Bi-weekly", 16, explanation("US Employee Pay", 16, 10, "Employee type", "Full-time")),
    assignment(202, 2, assignmentFields[1], "Standard PTO", 17, explanation("Standard PTO", 17, 10, "Employee type", "Full-time")),
    assignment(203, 2, assignmentFields[2], "Linear", 18, groupExplanation("Product Tools", 18, "Product")),
  ],
  3: [
    assignment(301, 3, assignmentFields[0], "Monthly", null, overrideExplanation("Monthly", "Bi-weekly"), 41),
    assignment(302, 3, assignmentFields[2], "Salesforce", 19, groupExplanation("Sales Access", 19, "Sales")),
  ],
  4: [
    assignment(401, 4, assignmentFields[0], "Bi-weekly", 11, explanation("California Pay Schedule", 11, 20, "State", "California")),
    assignment(402, 4, assignmentFields[1], "Flexible PTO", 15, explanation("Senior Employee PTO", 15, 15, "Tenure", "P5Y")),
    assignment(403, 4, assignmentFields[3], "Manager Harassment Training", 20, explanation("Manager Compliance", 20, 25, "Is manager", "true")),
  ],
};

function assignment(id: number, employeeId: number, fieldDef: AssignmentField, value: string, policyVersionId: number | null, explanationData: Record<string, unknown>, overrideId: number | null = null): Assignment {
  return { id, employee_id: employeeId, assignment_field_definition_id: fieldDef.id, value, source_policy_version_id: policyVersionId, source_override_id: overrideId, explanation: explanationData, effective_from: now, effective_until: null, assignment_field_definition: fieldDef };
}

function explanation(name: string, versionId: number, priority: number, fieldName: string, expected: string) {
  return { reason: "policy", policy: { id: versionId, name }, policy_version: { id: versionId, version_number: 1 }, origins: [{ type: "condition_match", matched_clauses: [{ conditions: [{ field: fieldName.toLowerCase().replaceAll(" ", "_"), operator: "=", expected, actual: expected, result: true }] }] }], selection: { field: fieldName, cardinality: "one", strategy: "priority", priority, candidates: [] } };
}

function groupExplanation(name: string, versionId: number, groupName: string) {
  return { reason: "policy", policy: { id: versionId, name }, policy_version: { id: versionId, version_number: 1 }, origins: [{ type: "group", group_id: versionId, group_name: groupName }], selection: { field: "Application access", cardinality: "many", strategy: "set_union", priority: 10, candidates: [] } };
}

function overrideExplanation(value: string, replaced: string) {
  return { reason: "override", override: { id: 41, value }, replaced_policy_assignments: [{ value: replaced, policy_name: "US Employee Pay" }] };
}

export const policies: Policy[] = [
  policy(1, "California Pay Schedule", "active", 20, [{ field: "state", operator: "=", value: "California" }], [{ assignment_field_definition_id: 1, value: "Bi-weekly" }], 37),
  policy(2, "Engineering Access", "active", 10, [{ field: "department", operator: "=", value: "Engineering" }], [{ assignment_field_definition_id: 3, value: "GitHub" }, { assignment_field_definition_id: 3, value: "Linear" }], 64),
  policy(3, "California Compliance", "active", 30, [{ field: "state", operator: "=", value: "California" }], [{ assignment_field_definition_id: 4, value: "CA Workplace Harassment" }], 42),
  policy(4, "Senior Employee PTO", "active", 15, [{ field: "tenure", operator: ">=", value: "P5Y" }], [{ assignment_field_definition_id: 2, value: "Flexible PTO" }], 29),
  policy(5, "Manager Compliance", "active", 25, [{ field: "is_manager", operator: "=", value: "true" }], [{ assignment_field_definition_id: 4, value: "Manager Harassment Training" }], 18),
  policy(6, "Legacy Commuter Benefit", "archived", 5, [{ field: "location", operator: "=", value: "New York" }], [{ assignment_field_definition_id: 5, value: "$180 monthly" }], 0),
];

function policy(id: number, name: string, status: Policy["status"], priority: number, conditions: Policy["versions"][number]["condition_group"]["conditions"], values: Policy["versions"][number]["values"], matches: number): Policy {
  const createdAt = `2026-0${Math.min(id + 1, 9)}-12T10:00:00`;
  return { id, name, status, created_at: createdAt, capabilities: { can_update: true, can_create_version: status !== "archived", can_activate: status !== "active", can_archive: status !== "archived" }, versions: [{ id: id + 10, policy_id: id, version_number: id === 1 ? 2 : 1, priority, effective_from: "2026-01-01", effective_until: null, created_at: createdAt, created_by: "Priya Shah", condition_group: { logical_operator: "and", conditions, child_groups: [] }, values: values.map((value) => ({ ...value, value: matches === 0 ? value.value : value.value })) }] };
}

export const policyImpacts: Record<number, PolicyImpact> = Object.fromEntries(
  policies.map((item, index) => [item.id, { policy_id: item.id, matched_employee_count: [37, 64, 42, 29, 18, 0][index], selected_employee_count: [37, 61, 42, 26, 18, 0][index], selected_assignment_count: [37, 122, 42, 26, 18, 0][index], matched_without_selected_assignment_count: [0, 3, 0, 3, 0, 0][index], suppressed_by_override_employee_count: item.id === 1 ? 1 : 0, complete: true }]),
);

export const assignmentSummary: AssignmentSummary = {
  employee_count: 248, employees_with_assignments: 244, employees_without_assignments: 4,
  assignment_count: 1426, policy_assignment_count: 1419, override_assignment_count: 7,
  field_count: 8, complete: true, conflicted_employee_count: 0,
  fields: [
    { assignment_field_definition: assignmentFields[0], assigned_employee_count: 246, assignment_count: 246 },
    { assignment_field_definition: assignmentFields[1], assigned_employee_count: 243, assignment_count: 243 },
    { assignment_field_definition: assignmentFields[2], assigned_employee_count: 231, assignment_count: 487 },
    { assignment_field_definition: assignmentFields[3], assigned_employee_count: 219, assignment_count: 332 },
  ],
};

export const groups: Group[] = [
  { id: 1, name: "Engineering" }, { id: 2, name: "People managers" }, { id: 3, name: "US employees" }, { id: 4, name: "New York office" },
];

export const groupEmployeeIds: Record<number, number[]> = {
  1: [1, 4],
  2: [4, 5, 6],
  3: [1, 2, 4, 5, 6, 7, 8],
  4: [2],
};

export const groupPolicyIds: Record<number, number[]> = {
  1: [2],
  2: [5],
  3: [1, 3],
  4: [],
};

export const overridesByEmployee: Record<number, EmployeeOverride[]> = {
  3: [{ id: 41, employee_id: 3, assignment_field_definition_id: 1, value: "Monthly", retired_at: null, assignment_field_definition: assignmentFields[0] }],
};

export const auditLogs: AuditLog[] = [
  { id: 1, actor: "Priya Shah", entity_type: "PolicyVersion", entity_id: 12, action: "created", before: null, after: { name: "California Leave Policy", priority: 30 }, timestamp: "2026-09-02T14:18:00Z" },
  { id: 2, actor: "Priya Shah", entity_type: "Employee", entity_id: 2, action: "changed", before: { department: "Design" }, after: { department: "Product" }, timestamp: "2026-09-02T13:03:00Z" },
  { id: 3, actor: "system", entity_type: "EmployeeAssignment", entity_id: 203, action: "created", before: null, after: { field: "Application access", value: "Linear" }, timestamp: "2026-09-02T13:03:00Z" },
  { id: 4, actor: "Priya Shah", entity_type: "EmployeeOverride", entity_id: 41, action: "created", before: null, after: { field: "Pay schedule", value: "Monthly" }, timestamp: "2026-09-01T16:42:00Z" },
];
