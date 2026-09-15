"use client";

import { Check, Eye, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { ManagerCombobox } from "./manager-combobox";
import { EmployeeAssignmentPreviewPanel } from "./employee-assignment-preview";
import { formatEmployeeId } from "@/lib/format";
import type {
  Employee,
  EmployeeAssignmentPreview,
  EmployeeManagerCandidate,
  EmployeeManagerSummary,
  EmployeeReferenceData,
} from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";
import { Button, SelectInput } from "@/components/ui";
import { StateCombobox } from "@/components/shared";

type EmployeeInput = Omit<Employee, "id" | "state_label">;
const createBlankEmployee = (): EmployeeInput => ({
  name: "",
  state: "",
  department: "",
  employee_type: "",
  location: "",
  start_date: new Date().toISOString().slice(0, 10),
  manager_id: null,
});

export function EmployeeEditor({
  employee,
  manager,
  referenceData: initialReferenceData,
  mfaEnabled = false,
  compact = false,
  trigger,
}: {
  employee?: Employee;
  manager?: EmployeeManagerSummary | null;
  referenceData?: EmployeeReferenceData;
  mfaEnabled?: boolean;
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
      : createBlankEmployee(),
  );
  const [preview, setPreview] = useState<EmployeeAssignmentPreview | null>(null);
  const [approval, setApproval] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [validationAttempted, setValidationAttempted] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [reauthenticationRequired, setReauthenticationRequired] = useState(false);
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [passwordInvalid, setPasswordInvalid] = useState(false);
  const [mfaInvalid, setMfaInvalid] = useState(false);
  const [referenceData, setReferenceData] = useState<EmployeeReferenceData | null>(
    initialReferenceData ?? null,
  );
  const [referenceLoading, setReferenceLoading] = useState(false);
  const [referenceError, setReferenceError] = useState("");
  useModalAccessibility(compact && open, () => {
    resetReauthentication();
    setOpen(false);
  });
  useEffect(() => {
    if (!compact || !success) return;
    const timeout = window.setTimeout(() => setSuccess(""), 4000);
    return () => window.clearTimeout(timeout);
  }, [compact, success]);

  const initialManagerCandidate: EmployeeManagerCandidate | undefined = data.manager_id
    ? {
        id: data.manager_id,
        label: manager
          ? `${manager.name} · ${formatEmployeeId(manager.id)}`
          : `Employee ${formatEmployeeId(data.manager_id)}`,
      }
    : undefined;
  const departments = referenceData?.departments ?? [];
  const employeeTypes = referenceData?.employee_types ?? [];
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
    resetReauthentication();
    setSuccess("");
    setError("");
  }

  function resetReauthentication() {
    setReauthenticationRequired(false);
    setPassword("");
    setMfaCode("");
    setPasswordInvalid(false);
    setMfaInvalid(false);
  }

  async function loadReferenceData() {
    if (referenceData || referenceLoading) return;
    setReferenceLoading(true);
    setReferenceError("");
    try {
      const response = await fetch("/api/backend/employees/reference-data");
      if (!response.ok) throw new Error("Employee options could not be loaded.");
      setReferenceData((await response.json()) as EmployeeReferenceData);
    } catch (reason) {
      setReferenceError(
        reason instanceof Error ? reason.message : "Employee options could not be loaded.",
      );
    } finally {
      setReferenceLoading(false);
    }
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
      setPreview(result as EmployeeAssignmentPreview);
      setApproval(result.approval?.token ?? null);
      resetReauthentication();
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
      if (reauthenticationRequired) {
        const missingPassword = !password;
        const missingMfaCode = mfaEnabled && !mfaCode;
        setPasswordInvalid(missingPassword);
        setMfaInvalid(missingMfaCode);
        if (missingPassword || missingMfaCode) {
          setError(
            missingMfaCode
              ? "Enter your password and MFA code to confirm this change."
              : "Enter your password to confirm this change.",
          );
          return;
        }

        const reauthenticationResponse = await fetch("/api/backend/auth/reauthenticate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password, ...(mfaCode ? { mfa_code: mfaCode } : {}) }),
        });
        if (!reauthenticationResponse.ok) {
          const failure = await requestFailure(reauthenticationResponse);
          setPasswordInvalid(failure.code === "invalid_current_password");
          setMfaInvalid(failure.code === "invalid_mfa_code");
          setError(failure.message);
          return;
        }
        resetReauthentication();
      }

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
      if (!response.ok) {
        const failure = await requestFailure(response);
        if (failure.code === "reauthentication_required") {
          setReauthenticationRequired(true);
          return;
        }
        throw new Error(failure.message || "The employee change could not be saved.");
      }
      setPreview(null);
      setApproval(null);
      resetReauthentication();
      setValidationAttempted(false);
      if (!employee) {
        setSuccess("Employee created and assignments resolved.");
        setData(createBlankEmployee());
        router.push("/employees");
      } else {
        setSuccess("Employee updated and assignments recalculated.");
        setOpen(false);
        router.refresh();
      }
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
          {success && !compact && (
            <div className="success-banner" role="status">
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
              <SelectInput
                required
                aria-invalid={validationAttempted && !data.department}
                value={data.department}
                onChange={(e) => update("department", e.target.value)}
              >
                <option value="" disabled>
                  Select a department
                </option>
                {departments.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </SelectInput>
            </label>
            <label className="field">
              <span className="field-label">
                Employment type <span className="required">Required</span>
              </span>
              <SelectInput
                required
                aria-invalid={validationAttempted && !data.employee_type}
                value={data.employee_type}
                onChange={(e) => update("employee_type", e.target.value)}
              >
                <option value="" disabled>
                  Select an employment type
                </option>
                {employeeTypes.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </SelectInput>
            </label>
            <label className="field">
              <span className="field-label">
                State <span className="required">Required</span>
              </span>
              <StateCombobox
                states={referenceData?.states ?? []}
                value={data.state}
                invalid={validationAttempted && !data.state}
                onChange={(value) => update("state", value)}
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
            <div className="field">
              <label className="field-label" htmlFor="manager">
                Manager
              </label>
              <ManagerCombobox
                employeeId={employee?.id}
                initialCandidate={initialManagerCandidate}
                onChange={(managerId) => update("manager_id", managerId)}
              />
            </div>
          </div>
        </div>
        {reauthenticationRequired && (
          <div
            className={`sensitive-confirmation employee-sensitive-confirmation${mfaEnabled ? " with-mfa" : ""}`}
          >
            <div className="sensitive-confirmation-copy">
              <strong>Confirm your identity</strong>
              <span>
                Your session needs fresh authentication before this reviewed change can be applied.
              </span>
            </div>
            <label className="field">
              <span className="field-label">
                Password <span className="required">Required</span>
              </span>
              <input
                className={`input${passwordInvalid ? " field-invalid" : ""}`}
                type="password"
                autoComplete="current-password"
                autoFocus
                aria-required="true"
                aria-invalid={passwordInvalid}
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  setPasswordInvalid(false);
                  setError("");
                }}
              />
            </label>
            {mfaEnabled && (
              <label className="field">
                <span className="field-label">
                  MFA code <span className="required">Required</span>
                </span>
                <input
                  className={`input${mfaInvalid ? " field-invalid" : ""}`}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  aria-required="true"
                  aria-invalid={mfaInvalid}
                  value={mfaCode}
                  onChange={(event) => {
                    setMfaCode(event.target.value);
                    setMfaInvalid(false);
                    setError("");
                  }}
                />
              </label>
            )}
          </div>
        )}
        <div className="form-footer employee-editor-footer">
          <div className="heading-actions">
            <Button variant="secondary" type="button" onClick={review} disabled={submitting}>
              <Eye size={14} />
              {submitting ? "Calculating…" : "Review assignments"}
            </Button>
            {preview && (
              <Button type="button" onClick={confirm} disabled={submitting}>
                <Check size={14} />
                {submitting
                  ? "Confirming…"
                  : reauthenticationRequired
                    ? "Authenticate and confirm"
                    : employee
                      ? "Confirm changes"
                      : "Create employee"}
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
          <EmployeeAssignmentPreviewPanel preview={preview} />
        )}
      </aside>
    </div>
  );

  if (!compact) return form;
  return (
    <>
      {success && (
        <div className="floating-message success-banner" role="status">
          <Check size={14} />
          {success}
        </div>
      )}
      <Button
        variant="secondary"
        onClick={() => {
          setSuccess("");
          setError("");
          resetReauthentication();
          setOpen(true);
          void loadReferenceData();
        }}
      >
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
                onClick={() => {
                  resetReauthentication();
                  setOpen(false);
                }}
                aria-label="Close editor"
              >
                <X size={16} />
              </button>
            </div>
            <div className="modal-body">
              {referenceLoading ? (
                <div className="empty-state compact">Loading employee options…</div>
              ) : referenceError ? (
                <div className="section-stack">
                  <div className="error-banner" role="alert">
                    {referenceError}
                  </div>
                  <Button variant="secondary" onClick={() => void loadReferenceData()}>
                    Try again
                  </Button>
                </div>
              ) : (
                form
              )}
            </div>
          </section>
        </div>
      )}
    </>
  );
}

type RequestFailure = { code?: string; message: string };

async function requestFailure(response: Response): Promise<RequestFailure> {
  const result = await response.json().catch(() => ({}));
  return {
    code: result.error?.code,
    message:
      result.error?.issues?.[0]?.message ??
      result.error?.message ??
      `Request failed with ${response.status}`,
  };
}
