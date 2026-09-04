"use client";

import { Check, CircleAlert, Clock3, Pencil, Plus, ShieldCheck, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { formatDate } from "@/lib/format";
import type { Assignment, AssignmentField, Employee, EmployeeOverride } from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";

type OverrideAction = "create" | "update" | "delete";
type PendingOverride = { action: OverrideAction; override?: EmployeeOverride; fieldId?: number; value?: string; approvalToken: string | null; added: number; removed: number; changed: number };

export function OverrideManager({ employee, fields, initialOverrides, history, apiConfigured }: { employee: Employee; fields: AssignmentField[]; initialOverrides: EmployeeOverride[]; history: Assignment[]; apiConfigured: boolean }) {
  const router = useRouter();
  const [overrides, setOverrides] = useState(initialOverrides);
  const [editing, setEditing] = useState<EmployeeOverride | "new" | null>(null);
  const [fieldId, setFieldId] = useState(fields[0]?.id ?? 0);
  const [value, setValue] = useState("");
  const [pending, setPending] = useState<PendingOverride | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useModalAccessibility(Boolean(editing || pending), () => { setEditing(null); setPending(null); });

  function openEditor(override?: EmployeeOverride) {
    setEditing(override ?? "new"); setFieldId(override?.assignment_field_definition_id ?? fields[0]?.id ?? 0); setValue(override?.value ?? ""); setError(""); setNotice("");
  }

  function buildChange(action: OverrideAction, override?: EmployeeOverride, selectedFieldId?: number, selectedValue?: string) {
    if (action === "create") return { type: "employee_override_change", action, employee_id: employee.id, assignment_field_definition_id: selectedFieldId, value: selectedValue };
    if (action === "update") return { type: "employee_override_change", action, employee_id: employee.id, override_id: override?.id, assignment_field_definition_id: selectedFieldId, value: selectedValue };
    return { type: "employee_override_change", action, employee_id: employee.id, override_id: override?.id };
  }

  async function preview(action: OverrideAction, override?: EmployeeOverride) {
    const selectedField = action === "delete" ? override?.assignment_field_definition_id : fieldId;
    const selectedValue = action === "delete" ? override?.value : value.trim();
    if (action !== "delete" && (!selectedField || !selectedValue)) { setError("Choose an assignment field and enter the manual value."); return; }
    setBusy(true); setError("");
    const change = buildChange(action, override, selectedField, selectedValue);
    try {
      if (!apiConfigured) {
        setPending({ action, override, fieldId: selectedField, value: selectedValue, approvalToken: null, added: action === "create" ? 1 : 0, removed: action === "delete" ? 1 : 0, changed: action === "update" ? 1 : 0 }); setEditing(null); return;
      }
      const response = await fetch("/api/backend/change-previews", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(change) });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.valid === false) throw new Error(result.error?.message ?? result.conflicts?.[0]?.message ?? "The override impact could not be calculated.");
      const impact = result.changes?.[0] ?? { added: [], removed: [], changed: [] };
      setPending({ action, override, fieldId: selectedField, value: selectedValue, approvalToken: result.approval?.token ?? null, added: impact.added?.length ?? 0, removed: impact.removed?.length ?? 0, changed: impact.changed?.length ?? 0 }); setEditing(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to preview the override."); }
    finally { setBusy(false); }
  }

  async function confirm() {
    if (!pending) return;
    setBusy(true); setError("");
    const change = buildChange(pending.action, pending.override, pending.fieldId, pending.value);
    try {
      let createdId = Math.max(...overrides.map((item) => item.id), 40) + 1;
      if (apiConfigured) {
        const directEndpoint = pending.action === "create" ? `/api/backend/employees/${employee.id}/overrides` : `/api/backend/employees/${employee.id}/overrides/${pending.override?.id}`;
        const endpoint = pending.approvalToken ? "/api/backend/change-executions" : directEndpoint;
        const method = pending.approvalToken ? "POST" : pending.action === "create" ? "POST" : pending.action === "update" ? "PATCH" : "DELETE";
        const directBody = pending.action === "delete" ? undefined : JSON.stringify({ assignment_field_definition_id: pending.fieldId, value: pending.value });
        const body = pending.approvalToken ? JSON.stringify({ approval_token: pending.approvalToken, change }) : directBody;
        const response = await fetch(endpoint, { method, headers: body ? { "Content-Type": "application/json" } : undefined, body });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.error?.message ?? result.detail ?? "The override could not be applied.");
        if (result.resources?.override_id) createdId = result.resources.override_id;
        else if (!pending.approvalToken && result.id) createdId = result.id;
      }
      if (pending.action === "delete") setOverrides((current) => current.filter((item) => item.id !== pending.override?.id));
      else {
        const field = fields.find((item) => item.id === pending.fieldId)!;
        const next: EmployeeOverride = { id: pending.override?.id ?? createdId, employee_id: employee.id, assignment_field_definition_id: pending.fieldId!, value: pending.value!, retired_at: null, assignment_field_definition: field };
        setOverrides((current) => pending.action === "create" ? [...current, next] : current.map((item) => item.id === next.id ? next : item));
      }
      setNotice(`Manual override ${pending.action === "delete" ? "removed" : pending.action === "create" ? "created" : "updated"}. Assignments were reconciled and audited.`); setPending(null); router.refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to apply the override."); }
    finally { setBusy(false); }
  }

  return <div className="section-stack">
    {(error || notice) && <div className={error ? "error-banner" : "success-banner"} role={error ? "alert" : "status"}>{error ? <CircleAlert size={14} /> : <Check size={14} />}{error || notice}</div>}
    <section className="panel"><div className="panel-header"><div><h2 className="panel-title">Manual overrides</h2><div className="panel-caption">Exceptions take precedence over every matching policy</div></div><button className="button secondary small" onClick={() => openEditor()}><Plus size={13} /> Add override</button></div><div className="panel-body">{overrides.length ? <div className="override-list">{overrides.map((override) => <div className="override-row" key={override.id}><div className="override-icon"><ShieldCheck size={15} /></div><div><div className="assignment-field">{override.assignment_field_definition.name}</div><div className="assignment-value">{override.value}</div><div className="secondary-cell">Override #{override.id} · currently active</div></div><div className="row-actions"><button className="icon-button" onClick={() => openEditor(override)} aria-label={`Edit ${override.assignment_field_definition.name} override`}><Pencil size={13} /></button><button className="icon-button danger" onClick={() => preview("delete", override)} aria-label={`Delete ${override.assignment_field_definition.name} override`}><Trash2 size={13} /></button></div></div>)}</div> : <div className="empty-state compact"><ShieldCheck size={18} /> No manual overrides. Policy resolution is authoritative.</div>}</div></section>
    <section className="panel"><div className="panel-header"><div><h2 className="panel-title">Assignment history</h2><div className="panel-caption">Current and retired records preserve the answer for any effective date</div></div><span className="badge"><Clock3 size={11} />{history.length} records</span></div><div className="panel-body flush"><table className="data-table"><thead><tr><th>Assignment</th><th>Value</th><th>Source</th><th>Effective</th></tr></thead><tbody>{history.map((assignment) => <tr key={assignment.id}><td><span className="primary-cell">{assignment.assignment_field_definition.name}</span></td><td>{assignment.value}</td><td><span className={`badge ${assignment.source_override_id ? "warning" : "accent"}`}>{assignment.source_override_id ? "Override" : "Policy"}</span></td><td><span className="secondary-cell" style={{ margin: 0 }}>{formatDate(assignment.effective_from)}{assignment.effective_until ? ` – ${formatDate(assignment.effective_until)}` : " – current"}</span></td></tr>)}</tbody></table>{history.length === 0 && <div className="empty-state compact">No assignment history yet.</div>}</div></section>
    {editing && <div className="modal-backdrop" role="presentation"><section className="form-dialog" role="dialog" aria-modal="true" aria-label={editing === "new" ? "Create manual override" : "Edit manual override"}><div className="modal-head"><div><h2>{editing === "new" ? "Create manual override" : "Edit manual override"}</h2><div className="panel-caption">You’ll review downstream impact before applying it.</div></div><button className="icon-button" onClick={() => setEditing(null)} aria-label="Close"><X size={16} /></button></div><div className="form-section"><label className="field"><span className="field-label">Assignment field</span><select className="select" value={fieldId} onChange={(event) => setFieldId(Number(event.target.value))}>{fields.map((field) => <option key={field.id} value={field.id}>{field.name} · {field.cardinality}</option>)}</select></label><label className="field"><span className="field-label">Manual value</span><input className="input" value={value} onChange={(event) => setValue(event.target.value)} placeholder="Enter the assignment value" /></label><div className="callout"><ShieldCheck size={14} /><span>This value wins over all policy results for the selected field until the override is removed.</span></div></div><div className="form-footer"><span className="form-hint">The preview will show replaced or restored assignments.</span><button className="button" disabled={busy} onClick={() => preview(editing === "new" ? "create" : "update", editing === "new" ? undefined : editing)}>{busy ? "Calculating…" : "Review impact"}</button></div></section></div>}
    {pending && <div className="modal-backdrop" role="presentation"><section className="confirm-card" role="dialog" aria-modal="true" aria-label="Confirm override"><div className="confirm-icon"><ShieldCheck size={18} /></div><h2>Confirm override {pending.action}</h2><p>This changes {pending.added + pending.removed + pending.changed} resolved assignment {pending.added + pending.removed + pending.changed === 1 ? "value" : "values"}: {pending.added} added, {pending.changed} changed, and {pending.removed} removed.</p><div className="heading-actions"><button className="button secondary" onClick={() => setPending(null)}>Cancel</button><button className={`button${pending.action === "delete" ? " danger-button" : ""}`} disabled={busy} onClick={confirm}>{busy ? "Applying…" : "Confirm and reconcile"}</button></div></section></div>}
  </div>;
}
