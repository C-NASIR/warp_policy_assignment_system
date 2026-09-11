"use client";

import { Check, CircleAlert, Eye, Plus, Sparkles, Trash2, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { initials } from "@/lib/format";
import type { AssignmentField, Condition, ConditionField, Employee, Policy } from "@/lib/types";

type BuilderCondition = Condition & { rowId: number };
type BuilderOutput = { rowId: number; assignment_field_definition_id: number; value: string };

export function PolicyBuilder({
  conditionFields,
  assignmentFields,
  employees,
  basePolicy,
  activateOnCreate = true,
}: {
  conditionFields: ConditionField[];
  assignmentFields: AssignmentField[];
  employees: Employee[];
  basePolicy?: Policy | null;
  activateOnCreate?: boolean;
}) {
  const router = useRouter();
  const baseVersion = basePolicy?.versions.at(-1);
  const hasAssignmentFields = assignmentFields.length > 0;
  const [name, setName] = useState(basePolicy?.name ?? "");
  const [priority, setPriority] = useState(baseVersion?.priority ?? 1);
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [effectiveUntil, setEffectiveUntil] = useState("");
  const [logic, setLogic] = useState<"and" | "or">(
    baseVersion?.condition_group.logical_operator ?? "and",
  );
  const initialConditions: Condition[] = baseVersion?.condition_group.conditions.length
    ? baseVersion.condition_group.conditions
    : conditionFields.length
      ? [
          {
            field: conditionFields[0].key,
            operator: conditionFields[0].allowed_operators[0],
            value: "",
          },
        ]
      : [];
  const [conditions, setConditions] = useState<BuilderCondition[]>(() =>
    initialConditions.map((item, index) => ({ ...item, rowId: index + 1 })),
  );
  const initialChild = baseVersion?.condition_group.child_groups[0];
  const [childLogic, setChildLogic] = useState<"and" | "or">(
    initialChild?.logical_operator ?? "or",
  );
  const [childConditions, setChildConditions] = useState<BuilderCondition[]>(() =>
    (initialChild?.conditions ?? []).map((item, index) => ({ ...item, rowId: index + 100 })),
  );
  const [outputs, setOutputs] = useState<BuilderOutput[]>(() =>
    (baseVersion?.values.length
      ? baseVersion.values
      : hasAssignmentFields
        ? [{ assignment_field_definition_id: 0, value: "" }]
        : []
    ).map((item, index) => ({ ...item, rowId: index + 1 })),
  );
  const [previewed, setPreviewed] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [approval, setApproval] = useState<string | null>(null);
  const [approvalRequestId, setApprovalRequestId] = useState<string | null>(null);
  const [engineAffected, setEngineAffected] = useState<number | null>(null);
  const [previewEmployees, setPreviewEmployees] = useState<
    { employee_id: number | null; employee_name: string }[]
  >([]);
  const [validationAttempted, setValidationAttempted] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  function setCondition(rowId: number, patch: Partial<BuilderCondition>) {
    setConditions((current) =>
      current.map((item) => (item.rowId === rowId ? { ...item, ...patch } : item)),
    );
    setPreviewed(false);
    setSuccess("");
  }
  function setOutput(rowId: number, patch: Partial<BuilderOutput>) {
    setOutputs((current) =>
      current.map((item) => (item.rowId === rowId ? { ...item, ...patch } : item)),
    );
    setPreviewed(false);
    setSuccess("");
  }
  function setChildCondition(rowId: number, patch: Partial<BuilderCondition>) {
    setChildConditions((current) =>
      current.map((item) => (item.rowId === rowId ? { ...item, ...patch } : item)),
    );
    setPreviewed(false);
    setSuccess("");
  }

  function versionPayload() {
    return {
      priority,
      effective_from: effectiveFrom,
      effective_until: effectiveUntil || null,
      condition_group: {
        logical_operator: logic,
        conditions: conditions.map((item) => ({
          field: item.field,
          operator: item.operator,
          value: item.value,
        })),
        child_groups: childConditions.length
          ? [
              {
                logical_operator: childLogic,
                conditions: childConditions.map((item) => ({
                  field: item.field,
                  operator: item.operator,
                  value: item.value,
                })),
                child_groups: [],
              },
            ]
          : [],
      },
      values: outputs.map((item) => ({
        assignment_field_definition_id: item.assignment_field_definition_id,
        value: item.value,
      })),
    };
  }

  async function review() {
    setValidationAttempted(true);
    if (!hasAssignmentFields) {
      setError("No assignment fields. Add assignment fields before you can create a policy.");
      return;
    }
    if (
      !name.trim() ||
      !effectiveFrom ||
      (effectiveUntil && effectiveUntil < effectiveFrom) ||
      [...conditions, ...childConditions].some((item) => !item.field || !item.value.trim()) ||
      outputs.length === 0 ||
      outputs.some((item) => !item.assignment_field_definition_id || !item.value.trim())
    ) {
      setError("Complete the highlighted fields before previewing this policy.");
      return;
    }
    setError("");
    setApproval(null);
    setApprovalRequestId(null);
    setEngineAffected(null);
    setPreviewEmployees([]);
    setReviewing(true);
    const version = versionPayload();
    const change = basePolicy
      ? {
          type: "policy_version_create",
          policy_id: basePolicy.id,
          version,
        }
      : {
          type: "policy_create",
          policy: {
            name: name.trim(),
            status: activateOnCreate ? "active" : "draft",
            ...version,
          },
        };
    try {
      const response = await fetch("/api/backend/change-previews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(change),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.valid === false)
        throw new Error(
          result.error?.message ??
            result.conflicts?.[0]?.message ??
            "The policy impact could not be calculated.",
        );
      setApproval(result.approval?.token ?? null);
      setApprovalRequestId(result.approval_request_id ?? null);
      setEngineAffected(result.affected_employee_count ?? 0);
      setPreviewEmployees(result.changes ?? []);
      if (result.approval_request_id) setSuccess("Preview submitted for independent approval.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to preview policy impact.");
      setReviewing(false);
      return;
    }
    setReviewing(false);
    setPreviewed(true);
  }

  async function save() {
    setSaving(true);
    setError("");
    const version = versionPayload();
    try {
      const change = basePolicy
        ? { type: "policy_version_create", policy_id: basePolicy.id, version }
        : null;
      const endpoint = approval
        ? "/api/backend/change-executions"
        : basePolicy
          ? `/api/backend/policies/${basePolicy.id}/versions`
          : "/api/backend/policies";
      const body = approval
        ? { approval_token: approval, change }
        : basePolicy
          ? version
          : { name: name.trim(), status: activateOnCreate ? "active" : "draft", ...version };
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(result.error?.message ?? result.detail ?? "The policy could not be saved.");
      setSuccess(
        basePolicy
          ? "New policy version created and assignments reconciled."
          : activateOnCreate
            ? "Policy created and assignments reconciled."
            : "Policy draft created for activation review.",
      );
      router.push(`/policies/${basePolicy?.id ?? result.resources?.policy_id ?? result.id}`);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save this policy.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="builder-shell">
      <div className="form-panel">
        <section className="form-section">
          <div className="form-section-title">Policy basics</div>
          <div className="form-section-description">
            Give admins a clear name and establish when this version should run.
          </div>
          {error && (
            <div className="error-banner">
              <CircleAlert size={13} style={{ display: "inline", marginRight: 6 }} />
              {error}
            </div>
          )}
          {success && (
            <div className="success-banner">
              <Check size={14} />
              {success}
            </div>
          )}
          <div className="field-grid">
            <label className="field full">
              <span className="field-label">
                Policy name <span className="required">Required</span>
              </span>
              <input
                className={`input${validationAttempted && !name.trim() ? " field-invalid" : ""}`}
                required
                aria-invalid={validationAttempted && !name.trim()}
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                  setPreviewed(false);
                }}
                disabled={Boolean(basePolicy)}
                placeholder="e.g. California Pay Schedule"
              />
            </label>
            <label className="field">
              <span className="field-label">Priority</span>
              <input
                className="input"
                type="number"
                value={priority}
                onChange={(event) => {
                  setPriority(Number(event.target.value));
                  setPreviewed(false);
                }}
              />
            </label>
            <div className="field">
              <span className="field-label">Resolution</span>
              <div className="callout" style={{ minHeight: 39, padding: "10px 11px" }}>
                <Sparkles size={13} />
                Higher priority wins
              </div>
            </div>
            <label className="field">
              <span className="field-label">
                Effective from <span className="required">Required</span>
              </span>
              <input
                className={`input${validationAttempted && !effectiveFrom ? " field-invalid" : ""}`}
                required
                aria-invalid={validationAttempted && !effectiveFrom}
                type="date"
                value={effectiveFrom}
                onChange={(event) => {
                  setEffectiveFrom(event.target.value);
                  setPreviewed(false);
                }}
              />
            </label>
            <label className="field">
              <span className="field-label">Effective until</span>
              <input
                className={`input${validationAttempted && Boolean(effectiveUntil && effectiveUntil < effectiveFrom) ? " field-invalid" : ""}`}
                aria-invalid={
                  validationAttempted && Boolean(effectiveUntil && effectiveUntil < effectiveFrom)
                }
                type="date"
                value={effectiveUntil}
                min={effectiveFrom}
                onChange={(event) => {
                  setEffectiveUntil(event.target.value);
                  setPreviewed(false);
                }}
              />
            </label>
          </div>
        </section>
        <section className="form-section">
          <div className="form-section-title">Who this applies to</div>
          <div className="form-section-description">
            Build the employee population from trusted facts and derived attributes.
          </div>
          <div className="rule-group">
            <div className="rule-group-head">
              <label className="logical-picker">
                Employees matching{" "}
                <select
                  className="select"
                  value={logic}
                  onChange={(event) => {
                    setLogic(event.target.value as "and" | "or");
                    setPreviewed(false);
                  }}
                >
                  <option value="and">ALL</option>
                  <option value="or">ANY</option>
                </select>{" "}
                of
              </label>
              <span className="badge accent">Backend evaluated</span>
            </div>
            {conditions.map((condition) => {
              const definition =
                conditionFields.find((item) => item.key === condition.field) ?? conditionFields[0];
              return (
                <div className="condition-row" key={condition.rowId}>
                  <select
                    className="select"
                    value={condition.field}
                    onChange={(event) => {
                      const next = conditionFields.find((item) => item.key === event.target.value);
                      setCondition(condition.rowId, {
                        field: event.target.value,
                        operator: next?.allowed_operators[0] ?? "=",
                        value: "",
                      });
                    }}
                  >
                    {conditionFields.map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  <select
                    className="select"
                    value={condition.operator}
                    onChange={(event) =>
                      setCondition(condition.rowId, {
                        operator: event.target.value as Condition["operator"],
                      })
                    }
                  >
                    {definition?.allowed_operators.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                  {definition?.input.type === "select" ? (
                    <select
                      className={`select${validationAttempted && !condition.value.trim() ? " field-invalid" : ""}`}
                      required
                      aria-invalid={validationAttempted && !condition.value.trim()}
                      value={condition.value}
                      onChange={(event) =>
                        setCondition(condition.rowId, { value: event.target.value })
                      }
                    >
                      <option value="">Choose value</option>
                      {definition.input.options.map((item) => (
                        <option value={item.value} key={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  ) : definition?.input.type === "resource" ? (
                    <select
                      className={`select${validationAttempted && !condition.value.trim() ? " field-invalid" : ""}`}
                      required
                      aria-invalid={validationAttempted && !condition.value.trim()}
                      value={condition.value}
                      onChange={(event) =>
                        setCondition(condition.rowId, { value: event.target.value })
                      }
                    >
                      <option value="">Choose employee</option>
                      {employees.map((item) => (
                        <option value={item.id} key={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className={`input${validationAttempted && !condition.value.trim() ? " field-invalid" : ""}`}
                      required
                      aria-invalid={validationAttempted && !condition.value.trim()}
                      type={
                        definition?.input.type === "date"
                          ? "date"
                          : definition?.input.type === "number"
                            ? "number"
                            : "text"
                      }
                      value={condition.value}
                      onChange={(event) =>
                        setCondition(condition.rowId, { value: event.target.value })
                      }
                      placeholder={definition?.input.placeholder ?? "Enter value"}
                    />
                  )}
                  <button
                    className="remove-button"
                    onClick={() => {
                      if (conditions.length > 1)
                        setConditions((current) =>
                          current.filter((item) => item.rowId !== condition.rowId),
                        );
                    }}
                    aria-label="Remove condition"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              );
            })}
            {childConditions.length > 0 && (
              <div className="rule-group nested">
                <div className="rule-group-head">
                  <label className="logical-picker">
                    Nested group matching{" "}
                    <select
                      className="select"
                      value={childLogic}
                      onChange={(event) => {
                        setChildLogic(event.target.value as "and" | "or");
                        setPreviewed(false);
                      }}
                    >
                      <option value="and">ALL</option>
                      <option value="or">ANY</option>
                    </select>{" "}
                    of
                  </label>
                  <button
                    className="remove-button"
                    onClick={() => {
                      setChildConditions([]);
                      setPreviewed(false);
                    }}
                    aria-label="Remove nested group"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
                {childConditions.map((condition) => {
                  const definition =
                    conditionFields.find((item) => item.key === condition.field) ??
                    conditionFields[0];
                  return (
                    <div className="condition-row" key={condition.rowId}>
                      <select
                        className="select"
                        value={condition.field}
                        onChange={(event) => {
                          const next = conditionFields.find(
                            (item) => item.key === event.target.value,
                          );
                          setChildCondition(condition.rowId, {
                            field: event.target.value,
                            operator: next?.allowed_operators[0] ?? "=",
                            value: "",
                          });
                        }}
                      >
                        {conditionFields.map((item) => (
                          <option key={item.key} value={item.key}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                      <select
                        className="select"
                        value={condition.operator}
                        onChange={(event) =>
                          setChildCondition(condition.rowId, {
                            operator: event.target.value as Condition["operator"],
                          })
                        }
                      >
                        {definition?.allowed_operators.map((item) => (
                          <option key={item}>{item}</option>
                        ))}
                      </select>
                      {definition?.input.type === "select" ? (
                        <select
                          className={`select${validationAttempted && !condition.value.trim() ? " field-invalid" : ""}`}
                          required
                          aria-invalid={validationAttempted && !condition.value.trim()}
                          value={condition.value}
                          onChange={(event) =>
                            setChildCondition(condition.rowId, { value: event.target.value })
                          }
                        >
                          <option value="">Choose value</option>
                          {definition.input.options.map((item) => (
                            <option value={item.value} key={item.value}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          className={`input${validationAttempted && !condition.value.trim() ? " field-invalid" : ""}`}
                          required
                          aria-invalid={validationAttempted && !condition.value.trim()}
                          type={
                            definition?.input.type === "date"
                              ? "date"
                              : definition?.input.type === "number"
                                ? "number"
                                : "text"
                          }
                          value={condition.value}
                          onChange={(event) =>
                            setChildCondition(condition.rowId, { value: event.target.value })
                          }
                          placeholder={definition?.input.placeholder ?? "Enter value"}
                        />
                      )}
                      <button
                        className="remove-button"
                        onClick={() =>
                          setChildConditions((current) =>
                            current.filter((item) => item.rowId !== condition.rowId),
                          )
                        }
                        aria-label="Remove nested condition"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  );
                })}
                <button
                  className="text-button"
                  onClick={() =>
                    setChildConditions((current) => [
                      ...current,
                      {
                        rowId: Math.max(...current.map((item) => item.rowId), 99) + 1,
                        field: conditionFields[0]?.key ?? "state",
                        operator: "=",
                        value: "",
                      },
                    ])
                  }
                >
                  <Plus size={13} /> Add nested condition
                </button>
              </div>
            )}
            <div className="heading-actions">
              <button
                className="text-button"
                onClick={() =>
                  setConditions((current) => [
                    ...current,
                    {
                      rowId: Math.max(...current.map((item) => item.rowId), 0) + 1,
                      field: conditionFields[0]?.key ?? "state",
                      operator: "=",
                      value: "",
                    },
                  ])
                }
              >
                <Plus size={13} /> Add condition
              </button>
              {childConditions.length === 0 && (
                <button
                  className="text-button"
                  onClick={() =>
                    setChildConditions([
                      {
                        rowId: 100,
                        field: conditionFields[0]?.key ?? "state",
                        operator: "=",
                        value: "",
                      },
                    ])
                  }
                >
                  <Plus size={13} /> Add nested group
                </button>
              )}
            </div>
          </div>
        </section>
        <section className="form-section">
          <div className="form-section-title">What gets assigned</div>
          <div className="form-section-description">
            Every policy produces one or more employee assignment values.
          </div>
          {!hasAssignmentFields && (
            <div className="error-banner" role="alert">
              <CircleAlert size={14} />
              <span>
                No assignment fields. <Link href="/settings">Add assignment fields</Link> before you
                can create a policy.
              </span>
            </div>
          )}
          <div className="output-list">
            {outputs.map((output) => {
              const field = assignmentFields.find(
                (item) => item.id === Number(output.assignment_field_definition_id),
              );
              return (
                <div className="output-row" key={output.rowId}>
                  <select
                    className={`select${validationAttempted && !output.assignment_field_definition_id ? " field-invalid" : ""}`}
                    required
                    aria-invalid={validationAttempted && !output.assignment_field_definition_id}
                    value={output.assignment_field_definition_id}
                    onChange={(event) =>
                      setOutput(output.rowId, {
                        assignment_field_definition_id: Number(event.target.value),
                      })
                    }
                  >
                    <option value={0}>Select assignment field</option>
                    {assignmentFields.map((item) => (
                      <option value={item.id} key={item.id}>
                        {item.name} · {item.cardinality}
                      </option>
                    ))}
                  </select>
                  <input
                    className={`input${validationAttempted && !output.value.trim() ? " field-invalid" : ""}`}
                    required
                    aria-invalid={validationAttempted && !output.value.trim()}
                    value={output.value}
                    onChange={(event) => setOutput(output.rowId, { value: event.target.value })}
                    placeholder={
                      !field
                        ? "Enter assignment value"
                        : field.cardinality === "many"
                          ? "e.g. GitHub"
                          : "e.g. Bi-weekly"
                    }
                  />
                  <button
                    className="remove-button assignment-remove"
                    disabled={outputs.length <= 1}
                    onClick={() => {
                      setOutputs((current) =>
                        current.filter((item) => item.rowId !== output.rowId),
                      );
                      setPreviewed(false);
                    }}
                    aria-label="Remove assignment"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              );
            })}
          </div>
          {hasAssignmentFields && (
            <button
              className="text-button"
              style={{ marginTop: 11 }}
              onClick={() =>
                setOutputs((current) => [
                  ...current,
                  {
                    rowId: Math.max(...current.map((item) => item.rowId), 0) + 1,
                    assignment_field_definition_id: 0,
                    value: "",
                  },
                ])
              }
            >
              <Plus size={13} /> Add another assignment
            </button>
          )}
        </section>
        <div className="form-footer">
          <span className="form-hint">
            {approvalRequestId
              ? `Approval request ${approvalRequestId} is pending.`
              : basePolicy
                ? "Previewing submits the exact change for an independent approval."
                : "Preview the affected population before this version is saved."}
          </span>
          <div className="heading-actions">
            {approvalRequestId && (
              <Link className="button secondary" href="/approvals">
                Open approvals
              </Link>
            )}
            <button
              className="button secondary"
              onClick={review}
              disabled={!hasAssignmentFields || reviewing || Boolean(approvalRequestId)}
            >
              <Eye size={14} />
              {reviewing ? "Calculating…" : "Preview impact"}
            </button>
            {previewed && !approvalRequestId && (
              <button className="button" onClick={save} disabled={!hasAssignmentFields || saving}>
                <Check size={14} />
                {saving ? "Saving…" : basePolicy ? "Create version" : "Create policy"}
              </button>
            )}
          </div>
        </div>
      </div>
      <aside className="form-panel preview-panel">
        {!previewed ? (
          <div className="preview-empty">
            <div className="preview-empty-icon">
              <Users size={19} />
            </div>
            <h3>Population impact</h3>
            <p>Preview to have the policy engine calculate the exact assignment impact.</p>
          </div>
        ) : (
          <>
            <div className="impact-hero">
              <Users size={17} />
              <div className="impact-number">{engineAffected ?? 0}</div>
              <div className="impact-label">employees will have resolved assignment changes</div>
            </div>
            <div className="preview-content">
              <div className="label">Affected employees</div>
              <div className="match-list">
                {previewEmployees.slice(0, 5).map((previewEmployee) => {
                  const employee = employees.find(
                    (item) => item.id === previewEmployee.employee_id,
                  );
                  return (
                    <div
                      className="match-person"
                      key={previewEmployee.employee_id ?? previewEmployee.employee_name}
                    >
                      <span className="person-cell">
                        <span className="avatar">{initials(previewEmployee.employee_name)}</span>
                        <span>
                          <span className="primary-cell">{previewEmployee.employee_name}</span>
                          <span className="secondary-cell">
                            {employee
                              ? `${employee.department} · ${employee.state}`
                              : "Employee record"}
                          </span>
                        </span>
                      </span>
                      <span className="badge success">Affected</span>
                    </div>
                  );
                })}
                {previewEmployees.length === 0 && (
                  <div className="empty-state" style={{ padding: 18 }}>
                    No employee assignments would change.
                  </div>
                )}
              </div>
              {previewEmployees.length > 5 && (
                <div className="results-count" style={{ marginTop: 9 }}>
                  + {previewEmployees.length - 5} more affected employees
                </div>
              )}
              <div className="label" style={{ marginTop: 19 }}>
                Assignments per match
              </div>
              {outputs.map((item) => (
                <div className="preview-assignment" key={item.rowId}>
                  <div>
                    <div className="preview-field">
                      {
                        assignmentFields.find(
                          (field) => field.id === Number(item.assignment_field_definition_id),
                        )?.name
                      }
                    </div>
                    <div className="preview-value">{item.value}</div>
                  </div>
                  <span className="preview-change added">+ Assign</span>
                </div>
              ))}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
