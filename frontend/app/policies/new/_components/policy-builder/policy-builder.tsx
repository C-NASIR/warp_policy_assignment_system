"use client";

import { Check, CircleAlert, Eye, Plus, RefreshCw, Sparkles, Trash2, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { BuilderCondition, ConditionRow, defaultCondition } from "./condition-row";
import { Badge, Button, WorkflowProgress } from "@/components/ui";
import { AssignmentValueInput } from "@/components/shared";
import { formatEmployeeId, initials } from "@/lib/format";
import type {
  AssignmentField,
  Condition,
  ConditionField,
  Employee,
  EmployeeReferenceData,
  Policy,
  PolicyAssignmentPreview,
} from "@/lib/types";
import styles from "./policy-builder.module.css";

type BuilderOutput = { rowId: number; assignment_field_definition_id: number; value: string };

export function PolicyBuilder({
  conditionFields,
  assignmentFields,
  employees,
  referenceData,
  basePolicy,
  activateOnCreate = true,
}: {
  conditionFields: ConditionField[];
  assignmentFields: AssignmentField[];
  employees: Employee[];
  referenceData: EmployeeReferenceData;
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
      ? [defaultCondition()]
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
  const [hasPreview, setHasPreview] = useState(false);
  const [previewStale, setPreviewStale] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewEmployees, setPreviewEmployees] = useState<
    PolicyAssignmentPreview["affected_employees"]
  >([]);
  const [previewAssignments, setPreviewAssignments] = useState<
    PolicyAssignmentPreview["assignments_per_match"]
  >([]);
  const [validationAttempted, setValidationAttempted] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  function markPreviewStale() {
    if (hasPreview) setPreviewStale(true);
    setSuccess("");
  }

  function setCondition(rowId: number, patch: Partial<BuilderCondition>) {
    setConditions((current) =>
      current.map((item) => (item.rowId === rowId ? { ...item, ...patch } : item)),
    );
    markPreviewStale();
  }
  function setOutput(rowId: number, patch: Partial<BuilderOutput>) {
    setOutputs((current) =>
      current.map((item) => (item.rowId === rowId ? { ...item, ...patch } : item)),
    );
    markPreviewStale();
  }
  function setChildCondition(rowId: number, patch: Partial<BuilderCondition>) {
    setChildConditions((current) =>
      current.map((item) => (item.rowId === rowId ? { ...item, ...patch } : item)),
    );
    markPreviewStale();
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
    if (hasPreview) setPreviewStale(true);
    setPreviewEmployees([]);
    setPreviewAssignments([]);
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
      const result = (await response
        .json()
        .catch(() => ({}))) as Partial<PolicyAssignmentPreview> & {
        error?: { message?: string };
      };
      if (!response.ok || result.conflict_message)
        throw new Error(
          result.error?.message ??
            result.conflict_message ??
            "The policy impact could not be calculated.",
        );
      setPreviewEmployees(result.affected_employees ?? []);
      setPreviewAssignments(result.assignments_per_match ?? []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to preview policy impact.");
      setReviewing(false);
      return;
    }
    setReviewing(false);
    setHasPreview(true);
    setPreviewStale(false);
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const version = versionPayload();
      const endpoint = basePolicy
        ? `/api/backend/policies/${basePolicy.id}/versions`
        : "/api/backend/policies";
      const body = basePolicy
        ? version
        : { name: name.trim(), status: activateOnCreate ? "active" : "draft", ...version };
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error?.message ?? "The policy could not be saved.");
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
    <>
      <WorkflowProgress
        currentStep={hasPreview && !previewStale ? 3 : hasPreview ? 2 : 1}
        steps={[
          { label: "Define", description: "Rules and outputs" },
          { label: "Preview", description: "Population impact" },
          {
            label: activateOnCreate ? "Activate" : "Save draft",
            description: basePolicy ? "Create version" : "Commit policy",
          },
        ]}
      />
      <div className="builder-shell">
        <div className="form-panel">
          <section className="form-section">
            <div className="form-section-heading">
              <span className="section-number">01</span>
              <div>
                <div className="form-section-title">Policy basics</div>
                <div className="form-section-description">
                  Name this version, set its priority, and define when it can take effect.
                </div>
              </div>
            </div>
            {error && (
              <div className="error-banner" id="policy-form-error" role="alert">
                <CircleAlert className={styles.inlineAlertIcon} size={13} />
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
                  aria-errormessage={
                    validationAttempted && !name.trim() ? "policy-form-error" : undefined
                  }
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                    markPreviewStale();
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
                    markPreviewStale();
                  }}
                />
              </label>
              <div className="field">
                <span className="field-label">Resolution</span>
                <div className={`callout ${styles.resolutionCallout}`}>
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
                  aria-errormessage={
                    validationAttempted && !effectiveFrom ? "policy-form-error" : undefined
                  }
                  type="date"
                  value={effectiveFrom}
                  onChange={(event) => {
                    setEffectiveFrom(event.target.value);
                    markPreviewStale();
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
                  aria-errormessage={
                    validationAttempted && Boolean(effectiveUntil && effectiveUntil < effectiveFrom)
                      ? "policy-form-error"
                      : undefined
                  }
                  type="date"
                  value={effectiveUntil}
                  min={effectiveFrom}
                  onChange={(event) => {
                    setEffectiveUntil(event.target.value);
                    markPreviewStale();
                  }}
                />
              </label>
            </div>
          </section>
          <section className="form-section">
            <div className="form-section-heading">
              <span className="section-number">02</span>
              <div>
                <div className="form-section-title">Eligibility conditions</div>
                <div className="form-section-description">
                  Build the employee population from trusted facts and derived attributes.
                </div>
              </div>
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
                      markPreviewStale();
                    }}
                  >
                    <option value="and">ALL</option>
                    <option value="or">ANY</option>
                  </select>{" "}
                  of
                </label>
                <Badge tone="accent">Backend evaluated</Badge>
              </div>
              {conditions.map((condition) => (
                <ConditionRow
                  key={condition.rowId}
                  condition={condition}
                  conditionFields={conditionFields}
                  employees={employees}
                  referenceData={referenceData}
                  validationAttempted={validationAttempted}
                  errorMessageId="policy-form-error"
                  removeDisabled={conditions.length <= 1}
                  removeLabel="Remove condition"
                  onChange={(patch) => setCondition(condition.rowId, patch)}
                  onRemove={() => {
                    setConditions((current) =>
                      current.filter((item) => item.rowId !== condition.rowId),
                    );
                    markPreviewStale();
                  }}
                />
              ))}
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
                          markPreviewStale();
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
                        markPreviewStale();
                      }}
                      aria-label="Remove nested group"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                  {childConditions.map((condition) => (
                    <ConditionRow
                      key={condition.rowId}
                      condition={condition}
                      conditionFields={conditionFields}
                      employees={employees}
                      referenceData={referenceData}
                      validationAttempted={validationAttempted}
                      errorMessageId="policy-form-error"
                      removeLabel="Remove nested condition"
                      onChange={(patch) => setChildCondition(condition.rowId, patch)}
                      onRemove={() => {
                        setChildConditions((current) =>
                          current.filter((item) => item.rowId !== condition.rowId),
                        );
                        markPreviewStale();
                      }}
                    />
                  ))}
                  <button
                    className="text-button"
                    onClick={() => {
                      setChildConditions((current) => [
                        ...current,
                        {
                          rowId: Math.max(...current.map((item) => item.rowId), 99) + 1,
                          ...defaultCondition(),
                        },
                      ]);
                      markPreviewStale();
                    }}
                  >
                    <Plus size={13} /> Add nested condition
                  </button>
                </div>
              )}
              <div className="heading-actions">
                <button
                  className="text-button"
                  onClick={() => {
                    setConditions((current) => [
                      ...current,
                      {
                        rowId: Math.max(...current.map((item) => item.rowId), 0) + 1,
                        ...defaultCondition(),
                      },
                    ]);
                    markPreviewStale();
                  }}
                >
                  <Plus size={13} /> Add condition
                </button>
                {childConditions.length === 0 && (
                  <button
                    className="text-button"
                    onClick={() => {
                      setChildConditions([
                        {
                          rowId: 100,
                          ...defaultCondition(),
                        },
                      ]);
                      markPreviewStale();
                    }}
                  >
                    <Plus size={13} /> Add nested group
                  </button>
                )}
              </div>
            </div>
          </section>
          <section className="form-section">
            <div className="form-section-heading">
              <span className="section-number">03</span>
              <div>
                <div className="form-section-title">Assignment outputs</div>
                <div className="form-section-description">
                  Employees who match the conditions above receive every output below.
                </div>
              </div>
            </div>
            {!hasAssignmentFields && (
              <div className="error-banner" role="alert">
                <CircleAlert size={14} />
                <span>
                  No assignment fields. <Link href="/settings">Add assignment fields</Link> before
                  you can create a policy.
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
                      aria-errormessage={
                        validationAttempted && !output.assignment_field_definition_id
                          ? "policy-form-error"
                          : undefined
                      }
                      value={output.assignment_field_definition_id}
                      onChange={(event) =>
                        setOutput(output.rowId, {
                          assignment_field_definition_id: Number(event.target.value),
                          value: "",
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
                    <AssignmentValueInput
                      field={field}
                      value={output.value}
                      invalid={validationAttempted && !output.value.trim()}
                      errorMessageId="policy-form-error"
                      onChange={(value) => setOutput(output.rowId, { value })}
                    />
                    <button
                      className="remove-button assignment-remove"
                      disabled={outputs.length <= 1}
                      onClick={() => {
                        setOutputs((current) =>
                          current.filter((item) => item.rowId !== output.rowId),
                        );
                        markPreviewStale();
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
                className={`text-button ${styles.addOutput}`}
                onClick={() => {
                  setOutputs((current) => [
                    ...current,
                    {
                      rowId: Math.max(...current.map((item) => item.rowId), 0) + 1,
                      assignment_field_definition_id: 0,
                      value: "",
                    },
                  ]);
                  markPreviewStale();
                }}
              >
                <Plus size={13} /> Add another assignment
              </button>
            )}
          </section>
          <div className="form-footer">
            <span className="form-hint">
              Preview the affected population before this {basePolicy ? "version" : "policy"} is
              saved.
            </span>
            <div className="heading-actions">
              <Button
                variant="secondary"
                onClick={review}
                disabled={!hasAssignmentFields || reviewing}
              >
                {previewStale ? <RefreshCw size={14} /> : <Eye size={14} />}
                {reviewing ? "Calculating…" : previewStale ? "Refresh impact" : "Preview impact"}
              </Button>
              {hasPreview && !previewStale && (
                <Button onClick={save} disabled={!hasAssignmentFields || saving}>
                  <Check size={14} />
                  {saving
                    ? "Saving…"
                    : basePolicy
                      ? "Create version"
                      : activateOnCreate
                        ? "Create and activate"
                        : "Save draft"}
                </Button>
              )}
            </div>
          </div>
        </div>
        <aside className="form-panel preview-panel" aria-label="Policy impact preview">
          {!hasPreview ? (
            <div className="preview-empty">
              <div className="preview-empty-icon">
                <Users size={19} />
              </div>
              <h3>Population impact</h3>
              <p>Preview to have the policy engine calculate the exact assignment impact.</p>
            </div>
          ) : (
            <>
              {previewStale && (
                <div className="stale-preview-banner" role="status">
                  <RefreshCw size={14} />
                  <span>
                    <strong>Impact preview out of date</strong>
                    Policy inputs changed. Refresh before saving.
                  </span>
                </div>
              )}
              <div className={previewStale ? "preview-stale-content" : undefined}>
                <div className="impact-hero">
                  <Users size={17} />
                  <div className="impact-number">{previewEmployees.length}</div>
                  <div className="impact-label">
                    employees will have resolved assignment changes
                  </div>
                  <div className="impact-meta">
                    <span>Priority {priority}</span>
                    <span>{previewAssignments.length} outputs</span>
                    <span>{activateOnCreate ? "Activates on save" : "Saves as draft"}</span>
                  </div>
                </div>
                <div className="preview-content">
                  <div className="label">Affected employees</div>
                  <div className="match-list">
                    {previewEmployees.slice(0, 5).map((previewEmployee) => {
                      return (
                        <div
                          className="match-person"
                          key={previewEmployee.employee_id ?? previewEmployee.employee_name}
                        >
                          <span className="person-cell">
                            <span className="avatar">
                              {initials(previewEmployee.employee_name)}
                            </span>
                            <span className="employee-identity">
                              <span className="primary-cell">{previewEmployee.employee_name}</span>
                              <span className="secondary-cell">
                                {previewEmployee.department} ·{" "}
                                {formatEmployeeId(previewEmployee.employee_id)}
                              </span>
                            </span>
                          </span>
                          <Badge tone="success">Affected</Badge>
                        </div>
                      );
                    })}
                    {previewEmployees.length === 0 && (
                      <div className={`empty-state ${styles.compactEmpty}`}>
                        No employee assignments would change.
                      </div>
                    )}
                  </div>
                  {previewEmployees.length > 5 && (
                    <div className={`results-count ${styles.moreResults}`}>
                      + {previewEmployees.length - 5} more affected employees
                    </div>
                  )}
                  <div className={`label ${styles.assignmentLabel}`}>Assignments per match</div>
                  {previewAssignments.map((item, index) => (
                    <div
                      className="preview-assignment"
                      key={`${item.assignment_field_definition_id}-${index}`}
                    >
                      <div>
                        <div className="preview-field">{item.assignment_field_name}</div>
                        <div className="preview-value">{item.value}</div>
                      </div>
                      <span className="preview-change added">+ Assign</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </aside>
      </div>
    </>
  );
}
