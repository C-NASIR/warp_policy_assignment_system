"use client";

import { Check, CircleAlert, Eye, Plus, Sparkles, Trash2, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { initials } from "@/lib/format";
import type { AssignmentField, Condition, ConditionField, Employee, Policy, RoleSummary } from "@/lib/types";

type BuilderCondition = Condition & { rowId: number };
type BuilderOutput = { rowId: number; assignment_field_definition_id: number; value: string };

export function PolicyBuilder({ conditionFields, assignmentFields, employees, automatableRoles, apiConfigured, basePolicy, activateOnCreate = true }: { conditionFields: ConditionField[]; assignmentFields: AssignmentField[]; employees: Employee[]; automatableRoles: RoleSummary[]; apiConfigured: boolean; basePolicy?: Policy | null; activateOnCreate?: boolean }) {
  const router = useRouter();
  const baseVersion = basePolicy?.versions.at(-1);
  const [name, setName] = useState(basePolicy?.name ?? "");
  const [priority, setPriority] = useState(baseVersion?.priority ?? 10);
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [effectiveUntil, setEffectiveUntil] = useState("");
  const [logic, setLogic] = useState<"and" | "or">(baseVersion?.condition_group.logical_operator ?? "and");
  const initialConditions: Condition[] = baseVersion?.condition_group.conditions.length ? baseVersion.condition_group.conditions : [{ field: "department", operator: "=", value: "Engineering" }];
  const [conditions, setConditions] = useState<BuilderCondition[]>(() => initialConditions.map((item, index) => ({ ...item, rowId: index + 1 })));
  const initialChild = baseVersion?.condition_group.child_groups[0];
  const [childLogic, setChildLogic] = useState<"and" | "or">(initialChild?.logical_operator ?? "or");
  const [childConditions, setChildConditions] = useState<BuilderCondition[]>(() => (initialChild?.conditions ?? []).map((item, index) => ({ ...item, rowId: index + 100 })));
  const [outputs, setOutputs] = useState<BuilderOutput[]>(() => (baseVersion ? baseVersion.values : [{ assignment_field_definition_id: assignmentFields[0]?.id ?? 1, value: "" }]).map((item, index) => ({ ...item, rowId: index + 1 })));
  const [automatedRoleIds, setAutomatedRoleIds] = useState<number[]>(baseVersion?.automated_role_ids ?? []);
  const [previewed, setPreviewed] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [approval, setApproval] = useState<string | null>(null);
  const [approvalRequestId, setApprovalRequestId] = useState<string | null>(null);
  const [engineAffected, setEngineAffected] = useState<number | null>(null);
  const [engineAccessAffected, setEngineAccessAffected] = useState<number | null>(null);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  const matchedEmployees = useMemo(() => employees.filter((employee) => {
    const results = conditions.map((condition) => matches(employee, condition, employees));
    if (childConditions.length) {
      const childResults = childConditions.map((condition) => matches(employee, condition, employees));
      results.push(childLogic === "and" ? childResults.every(Boolean) : childResults.some(Boolean));
    }
    return logic === "and" ? results.every(Boolean) : results.some(Boolean);
  }), [childConditions, childLogic, conditions, employees, logic]);

  function setCondition(rowId: number, patch: Partial<BuilderCondition>) {
    setConditions((current) => current.map((item) => item.rowId === rowId ? { ...item, ...patch } : item)); setPreviewed(false); setSuccess("");
  }
  function setOutput(rowId: number, patch: Partial<BuilderOutput>) {
    setOutputs((current) => current.map((item) => item.rowId === rowId ? { ...item, ...patch } : item)); setPreviewed(false); setSuccess("");
  }
  function setChildCondition(rowId: number, patch: Partial<BuilderCondition>) {
    setChildConditions((current) => current.map((item) => item.rowId === rowId ? { ...item, ...patch } : item)); setPreviewed(false); setSuccess("");
  }

  function versionPayload() {
    return { priority, effective_from: effectiveFrom, effective_until: effectiveUntil || null, condition_group: { logical_operator: logic, conditions: conditions.map((item) => ({ field: item.field, operator: item.operator, value: item.value })), child_groups: childConditions.length ? [{ logical_operator: childLogic, conditions: childConditions.map((item) => ({ field: item.field, operator: item.operator, value: item.value })), child_groups: [] }] : [] }, values: outputs.map((item) => ({ assignment_field_definition_id: item.assignment_field_definition_id, value: item.value })), automated_role_ids: automatedRoleIds };
  }

  async function review() {
    if (!name.trim() || [...conditions, ...childConditions].some((item) => !item.field || !item.value.trim()) || outputs.some((item) => !item.assignment_field_definition_id || !item.value.trim()) || (outputs.length === 0 && automatedRoleIds.length === 0)) {
      setError("Add a policy name, complete every rule, and select at least one assignment value or automated role."); return;
    }
    setError(""); setApproval(null); setApprovalRequestId(null); setEngineAffected(null); setEngineAccessAffected(null);
    if (apiConfigured && basePolicy) {
      setReviewing(true);
      const change = { type: "policy_version_create", policy_id: basePolicy.id, version: versionPayload() };
      try {
        const response = await fetch("/api/backend/change-previews", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(change) });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || result.valid === false) throw new Error(result.error?.message ?? result.conflicts?.[0]?.message ?? "The policy impact could not be calculated.");
        setApproval(result.approval?.token ?? null); setApprovalRequestId(result.approval_request_id ?? null); setEngineAffected(result.affected_employee_count ?? 0); setEngineAccessAffected(result.affected_user_count ?? 0);
        if (result.approval_request_id) setSuccess("Preview submitted for independent approval.");
      } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to preview policy impact."); setReviewing(false); return; }
      setReviewing(false);
    }
    setPreviewed(true);
  }

  async function save() {
    setSaving(true); setError("");
    const version = versionPayload();
    if (!apiConfigured) { setSuccess(basePolicy ? "New policy version created in demo mode." : "Policy created in demo mode with the impact shown."); setSaving(false); return; }
    try {
      const change = basePolicy ? { type: "policy_version_create", policy_id: basePolicy.id, version } : null;
      const endpoint = basePolicy && approval ? "/api/backend/change-executions" : basePolicy ? `/api/backend/policies/${basePolicy.id}/versions` : "/api/backend/policies";
      const body = basePolicy && approval ? { approval_token: approval, change } : basePolicy ? version : { name: name.trim(), status: activateOnCreate && automatedRoleIds.length === 0 ? "active" : "draft", ...version };
      const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error?.message ?? result.detail ?? "The policy could not be saved.");
      setSuccess(basePolicy ? "New policy version created and assignments reconciled." : activateOnCreate && automatedRoleIds.length === 0 ? "Policy created and assignments reconciled." : "Policy draft created for activation review.");
      router.push(`/policies/${basePolicy?.id ?? result.id}`); router.refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save this policy."); }
    finally { setSaving(false); }
  }

  return <div className="builder-shell">
    <div className="form-panel">
      <section className="form-section"><div className="form-section-title">Policy basics</div><div className="form-section-description">Give admins a clear name and establish when this version should run.</div>{error && <div className="error-banner"><CircleAlert size={13} style={{ display: "inline", marginRight: 6 }} />{error}</div>}{success && <div className="success-banner"><Check size={14} />{success}</div>}<div className="field-grid">
        <label className="field full"><span className="field-label">Policy name <span className="required">Required</span></span><input className="input" value={name} onChange={(event) => { setName(event.target.value); setPreviewed(false); }} disabled={Boolean(basePolicy)} placeholder="e.g. California Pay Schedule" /></label>
        <label className="field"><span className="field-label">Priority</span><input className="input" type="number" value={priority} onChange={(event) => { setPriority(Number(event.target.value)); setPreviewed(false); }} /></label>
        <div className="field"><span className="field-label">Resolution</span><div className="callout" style={{ minHeight: 39, padding: "10px 11px" }}><Sparkles size={13} />Higher priority wins</div></div>
        <label className="field"><span className="field-label">Effective from</span><input className="input" type="date" value={effectiveFrom} onChange={(event) => { setEffectiveFrom(event.target.value); setPreviewed(false); }} /></label>
        <label className="field"><span className="field-label">Effective until</span><input className="input" type="date" value={effectiveUntil} min={effectiveFrom} onChange={(event) => { setEffectiveUntil(event.target.value); setPreviewed(false); }} /></label>
      </div></section>
      <section className="form-section"><div className="form-section-title">Who this applies to</div><div className="form-section-description">Build the employee population from trusted facts and derived attributes.</div><div className="rule-group">
        <div className="rule-group-head"><label className="logical-picker">Employees matching <select className="select" value={logic} onChange={(event) => { setLogic(event.target.value as "and" | "or"); setPreviewed(false); }}><option value="and">ALL</option><option value="or">ANY</option></select> of</label><span className="badge accent">{matchedEmployees.length} match</span></div>
        {conditions.map((condition) => { const definition = conditionFields.find((item) => item.key === condition.field) ?? conditionFields[0]; return <div className="condition-row" key={condition.rowId}>
          <select className="select" value={condition.field} onChange={(event) => { const next = conditionFields.find((item) => item.key === event.target.value); setCondition(condition.rowId, { field: event.target.value, operator: next?.allowed_operators[0] ?? "=", value: "" }); }}>{conditionFields.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select>
          <select className="select" value={condition.operator} onChange={(event) => setCondition(condition.rowId, { operator: event.target.value as Condition["operator"] })}>{definition?.allowed_operators.map((item) => <option key={item}>{item}</option>)}</select>
          {definition?.input.type === "select" ? <select className="select" value={condition.value} onChange={(event) => setCondition(condition.rowId, { value: event.target.value })}><option value="">Choose value</option>{definition.input.options.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select> : definition?.input.type === "resource" ? <select className="select" value={condition.value} onChange={(event) => setCondition(condition.rowId, { value: event.target.value })}><option value="">Choose employee</option>{employees.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select> : <input className="input" type={definition?.input.type === "date" ? "date" : definition?.input.type === "number" ? "number" : "text"} value={condition.value} onChange={(event) => setCondition(condition.rowId, { value: event.target.value })} placeholder={definition?.input.placeholder ?? "Enter value"} />}
          <button className="remove-button" onClick={() => { if (conditions.length > 1) setConditions((current) => current.filter((item) => item.rowId !== condition.rowId)); }} aria-label="Remove condition"><Trash2 size={13} /></button>
        </div>; })}
        {childConditions.length > 0 && <div className="rule-group nested"><div className="rule-group-head"><label className="logical-picker">Nested group matching <select className="select" value={childLogic} onChange={(event) => { setChildLogic(event.target.value as "and" | "or"); setPreviewed(false); }}><option value="and">ALL</option><option value="or">ANY</option></select> of</label><button className="remove-button" onClick={() => { setChildConditions([]); setPreviewed(false); }} aria-label="Remove nested group"><Trash2 size={13} /></button></div>
          {childConditions.map((condition) => { const definition = conditionFields.find((item) => item.key === condition.field) ?? conditionFields[0]; return <div className="condition-row" key={condition.rowId}><select className="select" value={condition.field} onChange={(event) => { const next = conditionFields.find((item) => item.key === event.target.value); setChildCondition(condition.rowId, { field: event.target.value, operator: next?.allowed_operators[0] ?? "=", value: "" }); }}>{conditionFields.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select><select className="select" value={condition.operator} onChange={(event) => setChildCondition(condition.rowId, { operator: event.target.value as Condition["operator"] })}>{definition?.allowed_operators.map((item) => <option key={item}>{item}</option>)}</select>{definition?.input.type === "select" ? <select className="select" value={condition.value} onChange={(event) => setChildCondition(condition.rowId, { value: event.target.value })}><option value="">Choose value</option>{definition.input.options.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select> : <input className="input" type={definition?.input.type === "date" ? "date" : definition?.input.type === "number" ? "number" : "text"} value={condition.value} onChange={(event) => setChildCondition(condition.rowId, { value: event.target.value })} placeholder={definition?.input.placeholder ?? "Enter value"} />}<button className="remove-button" onClick={() => setChildConditions((current) => current.filter((item) => item.rowId !== condition.rowId))} aria-label="Remove nested condition"><Trash2 size={13} /></button></div>; })}
          <button className="text-button" onClick={() => setChildConditions((current) => [...current, { rowId: Math.max(...current.map((item) => item.rowId), 99) + 1, field: conditionFields[0]?.key ?? "state", operator: "=", value: "" }])}><Plus size={13} /> Add nested condition</button>
        </div>}
        <div className="heading-actions"><button className="text-button" onClick={() => setConditions((current) => [...current, { rowId: Math.max(...current.map((item) => item.rowId), 0) + 1, field: conditionFields[0]?.key ?? "state", operator: "=", value: "" }])}><Plus size={13} /> Add condition</button>{childConditions.length === 0 && <button className="text-button" onClick={() => setChildConditions([{ rowId: 100, field: conditionFields[0]?.key ?? "state", operator: "=", value: "" }])}><Plus size={13} /> Add nested group</button>}</div>
      </div></section>
      <section className="form-section"><div className="form-section-title">What gets assigned</div><div className="form-section-description">A policy can provide assignment values and grant roles that have explicitly opted into automation.</div><div className="output-list">{outputs.map((output) => { const field = assignmentFields.find((item) => item.id === Number(output.assignment_field_definition_id)); return <div className="output-row" key={output.rowId}>
        <select className="select" value={output.assignment_field_definition_id} onChange={(event) => setOutput(output.rowId, { assignment_field_definition_id: Number(event.target.value) })}>{assignmentFields.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.cardinality}</option>)}</select>
        <input className="input" value={output.value} onChange={(event) => setOutput(output.rowId, { value: event.target.value })} placeholder={field?.cardinality === "many" ? "e.g. GitHub" : "e.g. Bi-weekly"} />
        <button className="remove-button" onClick={() => { setOutputs((current) => current.filter((item) => item.rowId !== output.rowId)); setPreviewed(false); }} aria-label="Remove assignment"><Trash2 size={13} /></button>
      </div>; })}</div><button className="text-button" style={{ marginTop: 11 }} onClick={() => setOutputs((current) => [...current, { rowId: Math.max(...current.map((item) => item.rowId), 0) + 1, assignment_field_definition_id: assignmentFields[0]?.id ?? 1, value: "" }])}><Plus size={13} /> Add assignment</button></section>
      {automatableRoles.length > 0 && <section className="form-section"><div className="form-section-title">Automated access roles</div><div className="form-section-description">Matching linked users receive these roles. Explicit role assignments are never removed by policy reconciliation.</div><div className="role-options">{automatableRoles.map((role) => <label className="permission-option" key={role.id}><input type="checkbox" checked={automatedRoleIds.includes(role.id)} onChange={() => { setAutomatedRoleIds((current) => current.includes(role.id) ? current.filter((id) => id !== role.id) : [...current, role.id]); setPreviewed(false); setSuccess(""); }} /><span><strong>{role.name}</strong><small>Approved for policy automation</small></span></label>)}</div></section>}
      <div className="form-footer"><span className="form-hint">{approvalRequestId ? `Approval request ${approvalRequestId} is pending.` : apiConfigured && basePolicy ? "Previewing submits the exact change for an independent approval." : "Preview the affected population before this version is saved."}</span><div className="heading-actions">{approvalRequestId && <Link className="button secondary" href="/approvals">Open approvals</Link>}<button className="button secondary" onClick={review} disabled={reviewing || Boolean(approvalRequestId)}><Eye size={14} />{reviewing ? "Calculating…" : "Preview impact"}</button>{previewed && !approvalRequestId && <button className="button" onClick={save} disabled={saving}><Check size={14} />{saving ? "Saving…" : basePolicy ? "Create version" : "Create policy"}</button>}</div></div>
    </div>
    <aside className="form-panel preview-panel">{!previewed ? <div className="preview-empty"><div className="preview-empty-icon"><Users size={19} /></div><h3>Population impact</h3><p>Your current draft matches {matchedEmployees.length} employees. Preview to review the exact population and outputs.</p></div> : <><div className="impact-hero"><Users size={17} /><div className="impact-number">{engineAffected ?? matchedEmployees.length}</div><div className="impact-label">{engineAffected === null ? "employees match this policy version" : "employees will have resolved assignment changes"}</div>{engineAccessAffected !== null && <div className="form-hint">{engineAccessAffected} linked users will have access changes</div>}</div><div className="preview-content"><div className="label">Sample employees</div><div className="match-list">{matchedEmployees.slice(0, 5).map((employee) => <div className="match-person" key={employee.id}><span className="person-cell"><span className="avatar">{initials(employee.name)}</span><span><span className="primary-cell">{employee.name}</span><span className="secondary-cell">{employee.department} · {employee.state}</span></span></span><span className="badge success">Matches</span></div>)}{matchedEmployees.length === 0 && <div className="empty-state" style={{ padding: 18 }}>No employees currently match.</div>}</div>{matchedEmployees.length > 5 && <div className="results-count" style={{ marginTop: 9 }}>+ {matchedEmployees.length - 5} more matching employees</div>}<div className="label" style={{ marginTop: 19 }}>Assignments per match</div>{outputs.map((item) => <div className="preview-assignment" key={item.rowId}><div><div className="preview-field">{assignmentFields.find((field) => field.id === Number(item.assignment_field_definition_id))?.name}</div><div className="preview-value">{item.value}</div></div><span className="preview-change added">+ Assign</span></div>)}{automatedRoleIds.map((roleId) => <div className="preview-assignment" key={`role-${roleId}`}><div><div className="preview-field">Access role</div><div className="preview-value">{automatableRoles.find((role) => role.id === roleId)?.name}</div></div><span className="preview-change added">+ Grant</span></div>)}</div></>}</aside>
  </div>;
}

function matches(employee: Employee, condition: BuilderCondition, employees: Employee[]) {
  let actual: string | number | boolean = "";
  if (condition.field === "tenure") actual = new Date().getUTCFullYear() - new Date(employee.start_date).getUTCFullYear();
  else if (condition.field === "is_manager") actual = employees.some((item) => item.manager_id === employee.id);
  else if (condition.field === "direct_report_count") actual = employees.filter((item) => item.manager_id === employee.id).length;
  else if (condition.field === "reports_under") actual = employee.manager_id ?? "";
  else if (condition.field === "management_level") actual = employee.manager_id ? 1 : 0;
  else actual = String(employee[condition.field as keyof Employee] ?? "");
  const expectedRaw = condition.value.startsWith("P") ? condition.value.match(/\d+/)?.[0] ?? "0" : condition.value;
  const numeric = typeof actual === "number";
  const left = numeric ? Number(actual) : String(actual).toLowerCase();
  const right = numeric ? Number(expectedRaw) : String(expectedRaw).toLowerCase();
  if (condition.operator === "=") return String(left) === String(right);
  if (condition.operator === ">") return left > right;
  if (condition.operator === ">=") return left >= right;
  if (condition.operator === "<") return left < right;
  return left <= right;
}
