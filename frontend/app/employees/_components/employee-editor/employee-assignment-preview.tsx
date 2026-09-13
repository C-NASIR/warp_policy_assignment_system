import { Info } from "lucide-react";
import type { AssignmentPreview, EmployeeAssignmentPreview } from "@/lib/types";

type AssignmentChange = "added" | "changed" | "removed" | "unchanged";

type AssignmentRow = {
  fieldId: number;
  fieldName: string;
  before: AssignmentPreview[];
  after: AssignmentPreview[];
  change: AssignmentChange;
};

export function EmployeeAssignmentPreviewPanel({
  preview,
}: {
  preview: EmployeeAssignmentPreview;
}) {
  const rows = assignmentRows(preview.before_assignments, preview.after_assignments);
  const changedCount = rows.filter((row) => row.change !== "unchanged").length;
  const title =
    preview.type === "employee_create"
      ? preview.after_assignments.length === 0
        ? "No assignments will apply"
        : `${preview.after_assignments.length} assignment ${preview.after_assignments.length === 1 ? "value" : "values"} will apply`
      : changedCount === 0
        ? "No assignment changes"
        : `${changedCount} assignment ${changedCount === 1 ? "field" : "fields"} will change`;

  return (
    <>
      <div className="preview-header">
        <div className="preview-kicker">Resolution complete</div>
        <h3 className="preview-title">{title}</h3>
      </div>
      <div className="preview-content">
        {rows.length === 0 ? (
          <div className="secondary-cell">No policy currently assigns values to this employee.</div>
        ) : (
          rows.map((row) => (
            <div className="preview-assignment" key={row.fieldId}>
              <div>
                <div className="preview-field">{row.fieldName}</div>
                <div className="preview-value">{assignmentTransition(row)}</div>
                <div className="secondary-cell">{sourceTransition(row)}</div>
              </div>
              <span className={`preview-change ${row.change}`}>{changeLabel(row.change)}</span>
            </div>
          ))
        )}
      </div>
      <div className="form-section">
        <div className="callout">
          <Info size={14} />
          <span>This preview was calculated by the policy engine and can be safely approved.</span>
        </div>
      </div>
    </>
  );
}

function assignmentRows(before: AssignmentPreview[], after: AssignmentPreview[]): AssignmentRow[] {
  const beforeByField = groupByField(before);
  const afterByField = groupByField(after);
  const fieldIds = [...new Set([...beforeByField.keys(), ...afterByField.keys()])].sort(
    (left, right) => left - right,
  );

  return fieldIds.map((fieldId) => {
    const beforeAssignments = beforeByField.get(fieldId) ?? [];
    const afterAssignments = afterByField.get(fieldId) ?? [];
    return {
      fieldId,
      fieldName: (afterAssignments[0] ?? beforeAssignments[0]).assignment_field_name,
      before: beforeAssignments,
      after: afterAssignments,
      change: classifyChange(beforeAssignments, afterAssignments),
    };
  });
}

function groupByField(assignments: AssignmentPreview[]) {
  const groups = new Map<number, AssignmentPreview[]>();
  for (const assignment of assignments) {
    const values = groups.get(assignment.assignment_field_definition_id) ?? [];
    values.push(assignment);
    groups.set(assignment.assignment_field_definition_id, values);
  }
  return groups;
}

function classifyChange(before: AssignmentPreview[], after: AssignmentPreview[]): AssignmentChange {
  if (before.length === 0) return "added";
  if (after.length === 0) return "removed";
  const beforeKeys = before.map(assignmentKey).sort();
  const afterKeys = after.map(assignmentKey).sort();
  return beforeKeys.length === afterKeys.length &&
    beforeKeys.every((key, index) => key === afterKeys[index])
    ? "unchanged"
    : "changed";
}

function assignmentKey(assignment: AssignmentPreview) {
  return [
    assignment.value,
    assignment.source_type,
    assignment.source_id ?? "proposed",
    sourceName(assignment),
  ].join("\u0000");
}

function assignmentTransition(row: AssignmentRow) {
  const before = assignmentValues(row.before);
  const after = assignmentValues(row.after);
  if (row.change === "added" || row.change === "unchanged") return after;
  if (row.change === "removed") return before;
  return `${before} → ${after}`;
}

function sourceTransition(row: AssignmentRow) {
  const before = sourceNames(row.before);
  const after = sourceNames(row.after);
  if (row.change === "added" || row.change === "unchanged") return `From ${after}`;
  if (row.change === "removed") return `Previously from ${before}`;
  return before === after ? `From ${after}` : `Source: ${before} → ${after}`;
}

function assignmentValues(assignments: AssignmentPreview[]) {
  return assignments.map((assignment) => assignment.value).join(", ");
}

function sourceNames(assignments: AssignmentPreview[]) {
  return [...new Set(assignments.map(sourceName))].join(", ");
}

function sourceName(assignment: AssignmentPreview) {
  const policy = assignment.explanation.policy;
  if (policy && typeof policy === "object" && "name" in policy) {
    const name = policy.name;
    if (typeof name === "string") return name;
  }
  return assignment.source_type === "override" ? "Employee override" : "Policy rule";
}

function changeLabel(change: AssignmentChange) {
  if (change === "added") return "+ Add";
  if (change === "removed") return "Remove";
  if (change === "changed") return "Change";
  return "No change";
}
