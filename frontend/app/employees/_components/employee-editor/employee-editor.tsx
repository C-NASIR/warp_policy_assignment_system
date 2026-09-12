"use client";

import { Check, Eye, Info, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { ReactNode, useMemo, useState } from "react";
import type { AssignmentField, Employee, EmployeeReferenceData } from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";
import { Button } from "@/components/ui";

type EmployeeInput = Omit<Employee, "id">;
type PreviewItem = {
  field: string;
  value: string;
  source: string;
  change: "added" | "changed" | "unchanged";
};

const createBlankEmployee = (referenceData: EmployeeReferenceData): EmployeeInput => ({
  name: "",
  state: "",
  department: "",
  employee_type: referenceData.employee_types[0] ?? "",
  location: "",
  start_date: new Date().toISOString().slice(0, 10),
  manager_id: null,
});

export function EmployeeEditor({
  employee,
  employees,
  fields,
  referenceData,
  compact = false,
  trigger,
}: {
  employee?: Employee;
  employees: Employee[];
  fields: AssignmentField[];
  referenceData: EmployeeReferenceData;
  compact?: boolean;
  trigger?: ReactNode;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(!compact);
  const [data, setData] = useState<EmployeeInput>(() =>
    employee
      ? {
          name: employee.name,
          state: employee.state,
          department: employee.department,
          employee_type: employee.employee_type,
          location: employee.location,
          start_date: employee.start_date,
          manager_id: employee.manager_id,
        }
      : createBlankEmployee(referenceData),
  );
  const [preview, setPreview] = useState<PreviewItem[] | null>(null);
  const [approval, setApproval] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [validationAttempted, setValidationAttempted] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  useModalAccessibility(compact && open, () => setOpen(false));

  const managers = employees.filter((item) => item.id !== employee?.id);
  const departments = referenceData.departments;
  const employeeTypes = referenceData.employee_types;
  const payload = useMemo(
    () => ({
      ...data,
      location: data.location?.trim() || null,
      manager_id: data.manager_id ? Number(data.manager_id) : null,
    }),
    [data],
  );

  function update<K extends keyof EmployeeInput>(key: K, value: EmployeeInput[K]) {
    setData((current) => ({ ...current, [key]: value }));
    setPreview(null);
    setApproval(null);
    setSuccess("");
    setError("");
  }

  const change = employee
    ? { type: "employee_update", employee_id: employee.id, changes: payload }
    : { type: "employee_create", employee: payload };

  async function review() {
    setValidationAttempted(true);
    if (
      !payload.name.trim() ||
      !payload.state.trim() ||
      !payload.department ||
      !payload.employee_type ||
      !payload.start_date
    ) {
      setError("Complete every required employee field before reviewing assignments.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const response = await fetch("/api/backend/change-previews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(change),
      });
      const result = await response.json();
      if (!response.ok || result.valid === false)
        throw new Error(
          result.error?.message ??
            result.conflicts?.[0]?.message ??
            "The assignment preview could not be calculated.",
        );
      const affected =
        result.changes?.find(
          (item: { employee_id: number | null }) => item.employee_id === (employee?.id ?? null),
        ) ?? result.changes?.[0];
      const after = (affected?.after ?? []).map(
        (item: {
          assignment_field_name: string;
          value: string;
          explanation?: { policy?: { name?: string } };
        }) => ({
          field: item.assignment_field_name,
          value: item.value,
          source: item.explanation?.policy?.name ?? "Policy rule",
          change: "added" as const,
        }),
      );
      setPreview(after);
      setApproval(result.approval?.token ?? null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to preview this change.");
    } finally {
      setSubmitting(false);
    }
  }

  async function confirm() {
    setSubmitting(true);
    setError("");
    try {
      const endpoint = approval
        ? "/api/backend/change-executions"
        : employee
          ? `/api/backend/employees/${employee.id}`
          : "/api/backend/employees";
      const response = await fetch(endpoint, {
        method: approval ? "POST" : employee ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(approval ? { approval_token: approval, change } : payload),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(result.error?.message ?? "The employee change could not be saved.");
      setSuccess(
        employee
          ? "Employee and downstream assignments updated."
          : "Employee created and assignments resolved.",
      );
      if (!employee) {
        setData(createBlankEmployee(referenceData));
        setPreview(null);
        setApproval(null);
        setValidationAttempted(false);
        router.push("/employees");
      } else router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save this change.");
    } finally {
      setSubmitting(false);
    }
  }

  const form = (
    <div className="form-shell">
      <div className="form-panel">
        <div className="form-section">
          <div className="form-section-title">Employment details</div>
          <div className="form-section-description">
            These facts are evaluated against every active policy rule.
          </div>
          {error && <div className="error-banner">{error}</div>}
          {success && (
            <div className="success-banner">
              <Check size={14} />
              {success}
            </div>
          )}
          <div className="field-grid">
            <label className="field full">
              <span className="field-label">
                Full name <span className="required">Required</span>
              </span>
              <input
                className={`input${validationAttempted && !data.name.trim() ? " field-invalid" : ""}`}
                required
                aria-invalid={validationAttempted && !data.name.trim()}
                value={data.name}
                onChange={(e) => update("name", e.target.value)}
                placeholder="e.g. Avery Chen"
              />
            </label>
            <label className="field">
              <span className="field-label">
                Department <span className="required">Required</span>
              </span>
              <input
                className={`input${validationAttempted && !data.department ? " field-invalid" : ""}`}
                required
                aria-invalid={validationAttempted && !data.department}
                list="department-options"
                value={data.department}
                onChange={(e) => update("department", e.target.value)}
                placeholder="Enter or choose a department"
              />
              <datalist id="department-options">
                {departments.map((item) => (
                  <option key={item} value={item} />
                ))}
              </datalist>
            </label>
            <label className="field">
              <span className="field-label">
                Employment type <span className="required">Required</span>
              </span>
              <input
                className={`input${validationAttempted && !data.employee_type ? " field-invalid" : ""}`}
                required
                aria-invalid={validationAttempted && !data.employee_type}
                list="employee-type-options"
                value={data.employee_type}
                onChange={(e) => update("employee_type", e.target.value)}
                placeholder="Enter or choose an employment type"
              />
              <datalist id="employee-type-options">
                {employeeTypes.map((item) => (
                  <option key={item} value={item} />
                ))}
              </datalist>
            </label>
            <label className="field">
              <span className="field-label">
                State or region <span className="required">Required</span>
              </span>
              <input
                className={`input${validationAttempted && !data.state.trim() ? " field-invalid" : ""}`}
                required
                aria-invalid={validationAttempted && !data.state.trim()}
                value={data.state}
                onChange={(e) => update("state", e.target.value)}
                placeholder="e.g. California"
              />
            </label>
            <label className="field">
              <span className="field-label">Work location</span>
              <input
                className="input"
                value={data.location ?? ""}
                onChange={(e) => update("location", e.target.value)}
                placeholder="e.g. San Francisco"
              />
            </label>
            <label className="field">
              <span className="field-label">
                Start date <span className="required">Required</span>
              </span>
              <input
                className={`input${validationAttempted && !data.start_date ? " field-invalid" : ""}`}
                required
                aria-invalid={validationAttempted && !data.start_date}
                type="date"
                value={data.start_date}
                onChange={(e) => update("start_date", e.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">Manager</span>
              <select
                className="select"
                value={data.manager_id ?? ""}
                onChange={(e) =>
                  update("manager_id", e.target.value ? Number(e.target.value) : null)
                }
              >
                <option value="">No manager</option>
                {managers.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <div className="form-footer">
          <span className="form-hint">
            Checks {fields.length} assignment fields. Nothing is saved until you confirm.
          </span>
          <div className="heading-actions">
            <Button variant="secondary" type="button" onClick={review} disabled={submitting}>
              <Eye size={14} />
              {submitting ? "Calculating…" : "Review assignments"}
            </Button>
            {preview && (
              <Button type="button" onClick={confirm} disabled={submitting}>
                <Check size={14} />
                {employee ? "Confirm changes" : "Create employee"}
              </Button>
            )}
          </div>
        </div>
      </div>
      <aside className="form-panel preview-panel">
        {!preview ? (
          <div className="preview-empty">
            <div className="preview-empty-icon">
              <Sparkles size={19} />
            </div>
            <h3>Assignment preview</h3>
            <p>
              Complete the employee profile, then review exactly which policies and assignments will
              apply.
            </p>
          </div>
        ) : (
          <>
            <div className="preview-header">
              <div className="preview-kicker">Resolution complete</div>
              <h3 className="preview-title">{preview.length} assignment values will apply</h3>
            </div>
            <div className="preview-content">
              {preview.map((item, index) => (
                <div className="preview-assignment" key={`${item.field}-${item.value}-${index}`}>
                  <div>
                    <div className="preview-field">{item.field}</div>
                    <div className="preview-value">{item.value}</div>
                    <div className="secondary-cell">From {item.source}</div>
                  </div>
                  <span className={`preview-change ${item.change}`}>
                    {item.change === "unchanged"
                      ? "No change"
                      : item.change === "added"
                        ? "+ Add"
                        : "Change"}
                  </span>
                </div>
              ))}
            </div>
            <div className="form-section">
              <div className="callout">
                <Info size={14} />
                <span>
                  This preview was calculated by the policy engine and can be safely approved.
                </span>
              </div>
            </div>
          </>
        )}
      </aside>
    </div>
  );

  if (!compact) return form;
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        {trigger}
      </Button>
      {open && (
        <div className="modal-backdrop" role="presentation">
          <section
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-label="Edit employee"
          >
            <div className="modal-head">
              <h2>Edit {employee?.name}</h2>
              <button
                className="icon-button"
                onClick={() => setOpen(false)}
                aria-label="Close editor"
              >
                <X size={16} />
              </button>
            </div>
            <div className="modal-body">{form}</div>
          </section>
        </div>
      )}
    </>
  );
}
