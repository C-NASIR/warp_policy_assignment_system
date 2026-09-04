"use client";

import { Check, Eye, Info, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { ReactNode, useMemo, useState } from "react";
import type { Assignment, AssignmentField, Employee } from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";

type EmployeeInput = Omit<Employee, "id">;
type PreviewItem = { field: string; value: string; source: string; change: "added" | "changed" | "unchanged" };

const blankEmployee: EmployeeInput = { name: "", state: "", department: "", employee_type: "Full-time", location: "", start_date: new Date().toISOString().slice(0, 10), manager_id: null };

export function EmployeeEditor({
  employee,
  employees,
  fields,
  currentAssignments = [],
  apiConfigured,
  compact = false,
  trigger,
}: {
  employee?: Employee;
  employees: Employee[];
  fields: AssignmentField[];
  currentAssignments?: Assignment[];
  apiConfigured: boolean;
  compact?: boolean;
  trigger?: ReactNode;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(!compact);
  const [data, setData] = useState<EmployeeInput>(employee ? { name: employee.name, state: employee.state, department: employee.department, employee_type: employee.employee_type, location: employee.location, start_date: employee.start_date, manager_id: employee.manager_id } : blankEmployee);
  const [preview, setPreview] = useState<PreviewItem[] | null>(null);
  const [approval, setApproval] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  useModalAccessibility(compact && open, () => setOpen(false));

  const managers = employees.filter((item) => item.id !== employee?.id);
  const departments = [...new Set([...employees.map((item) => item.department), "Engineering", "Product", "Sales", "Design", "Support", "People"])] .sort();
  const payload = useMemo(() => ({ ...data, location: data.location?.trim() || null, manager_id: data.manager_id ? Number(data.manager_id) : null }), [data]);

  function update<K extends keyof EmployeeInput>(key: K, value: EmployeeInput[K]) {
    setData((current) => ({ ...current, [key]: value }));
    setPreview(null); setApproval(null); setSuccess(""); setError("");
  }

  function localAssignments(): PreviewItem[] {
    const items: Omit<PreviewItem, "change">[] = [];
    if (payload.state.toLowerCase().includes("california")) {
      items.push({ field: "Pay schedule", value: "Bi-weekly", source: "California Pay Schedule" });
      items.push({ field: "Compliance training", value: "CA Workplace Harassment", source: "California Compliance" });
    } else if (payload.employee_type === "Full-time") {
      items.push({ field: "Pay schedule", value: "Bi-weekly", source: "US Employee Pay" });
    } else {
      items.push({ field: "Pay schedule", value: "Monthly", source: "Contractor Pay Schedule" });
    }
    if (payload.employee_type === "Full-time") items.push({ field: "Vacation policy", value: "Standard PTO", source: "Standard PTO" });
    if (payload.department === "Engineering") {
      items.push({ field: "Application access", value: "GitHub", source: "Engineering Access" });
      items.push({ field: "Application access", value: "Linear", source: "Engineering Access" });
      items.push({ field: "Equipment stipend", value: "$1,000 annual", source: "Engineering Equipment" });
    }
    const currentByField = new Map(currentAssignments.map((item) => [item.assignment_field_definition.name, item.value]));
    return items.map((item) => ({ ...item, change: !currentByField.has(item.field) ? "added" : currentByField.get(item.field) !== item.value ? "changed" : "unchanged" }));
  }

  const change = employee ? { type: "employee_update", employee_id: employee.id, changes: payload } : { type: "employee_create", employee: payload };

  async function review() {
    if (!payload.name || !payload.state || !payload.department || !payload.employee_type || !payload.start_date) {
      setError("Complete every required employee field before reviewing assignments.");
      return;
    }
    setError(""); setSubmitting(true);
    if (!apiConfigured) {
      setPreview(localAssignments()); setSubmitting(false); return;
    }
    try {
      const response = await fetch("/api/backend/change-previews", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(change) });
      const result = await response.json();
      if (!response.ok || result.valid === false) throw new Error(result.error?.message ?? result.conflicts?.[0]?.message ?? "The assignment preview could not be calculated.");
      const affected = result.changes?.find((item: { employee_id: number | null }) => item.employee_id === (employee?.id ?? null)) ?? result.changes?.[0];
      const after = (affected?.after ?? []).map((item: { assignment_field_name: string; value: string; explanation?: { policy?: { name?: string } } }) => ({ field: item.assignment_field_name, value: item.value, source: item.explanation?.policy?.name ?? "Policy rule", change: "added" as const }));
      setPreview(after); setApproval(result.approval?.token ?? null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to preview this change.");
    } finally { setSubmitting(false); }
  }

  async function confirm() {
    setSubmitting(true); setError("");
    if (!apiConfigured) {
      setSuccess(employee ? "Employee updated in demo mode. The assignment preview reflects the new profile." : "Employee created in demo mode with the assignments shown.");
      setSubmitting(false); return;
    }
    try {
      const endpoint = approval ? "/api/backend/change-executions" : employee ? `/api/backend/employees/${employee.id}` : "/api/backend/employees";
      const response = await fetch(endpoint, { method: approval ? "POST" : employee ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(approval ? { approval_token: approval, change } : payload) });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error?.message ?? "The employee change could not be saved.");
      setSuccess(employee ? "Employee and downstream assignments updated." : "Employee created and assignments resolved.");
      router.refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save this change."); }
    finally { setSubmitting(false); }
  }

  const form = (
    <div className="form-shell">
      <div className="form-panel">
        <div className="form-section"><div className="form-section-title">Employment details</div><div className="form-section-description">These facts are evaluated against every active policy rule.</div>
          {error && <div className="error-banner">{error}</div>}{success && <div className="success-banner"><Check size={14} />{success}</div>}
          <div className="field-grid">
            <label className="field full"><span className="field-label">Full name <span className="required">Required</span></span><input className="input" value={data.name} onChange={(e) => update("name", e.target.value)} placeholder="e.g. Avery Chen" /></label>
            <label className="field"><span className="field-label">Department <span className="required">Required</span></span><select className="select" value={data.department} onChange={(e) => update("department", e.target.value)}><option value="">Select department</option>{departments.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label className="field"><span className="field-label">Employment type <span className="required">Required</span></span><select className="select" value={data.employee_type} onChange={(e) => update("employee_type", e.target.value)}><option>Full-time</option><option>Part-time</option><option>Contractor</option><option>Intern</option></select></label>
            <label className="field"><span className="field-label">State or region <span className="required">Required</span></span><input className="input" value={data.state} onChange={(e) => update("state", e.target.value)} placeholder="e.g. California" /></label>
            <label className="field"><span className="field-label">Work location</span><input className="input" value={data.location ?? ""} onChange={(e) => update("location", e.target.value)} placeholder="e.g. San Francisco" /></label>
            <label className="field"><span className="field-label">Start date <span className="required">Required</span></span><input className="input" type="date" value={data.start_date} onChange={(e) => update("start_date", e.target.value)} /></label>
            <label className="field"><span className="field-label">Manager</span><select className="select" value={data.manager_id ?? ""} onChange={(e) => update("manager_id", e.target.value ? Number(e.target.value) : null)}><option value="">No manager</option>{managers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          </div>
        </div>
        <div className="form-footer"><span className="form-hint">Checks {fields.length} assignment fields. Nothing is saved until you confirm.</span><div className="heading-actions"><button className="button secondary" type="button" onClick={review} disabled={submitting}><Eye size={14} />{submitting ? "Calculating…" : "Review assignments"}</button>{preview && <button className="button" type="button" onClick={confirm} disabled={submitting}><Check size={14} />{employee ? "Confirm changes" : "Create employee"}</button>}</div></div>
      </div>
      <aside className="form-panel preview-panel">
        {!preview ? <div className="preview-empty"><div className="preview-empty-icon"><Sparkles size={19} /></div><h3>Assignment preview</h3><p>Complete the employee profile, then review exactly which policies and assignments will apply.</p></div> : <><div className="preview-header"><div className="preview-kicker">Resolution complete</div><h3 className="preview-title">{preview.length} assignment values will apply</h3></div><div className="preview-content">{preview.map((item, index) => <div className="preview-assignment" key={`${item.field}-${item.value}-${index}`}><div><div className="preview-field">{item.field}</div><div className="preview-value">{item.value}</div><div className="secondary-cell">From {item.source}</div></div><span className={`preview-change ${item.change}`}>{item.change === "unchanged" ? "No change" : item.change === "added" ? "+ Add" : "Change"}</span></div>)}</div><div className="form-section"><div className="callout"><Info size={14} /><span>{apiConfigured ? "This preview was calculated by the policy engine and can be safely approved." : "Demo preview uses the same employee facts the connected policy engine evaluates."}</span></div></div></>}
      </aside>
    </div>
  );

  if (!compact) return form;
  return <><button className="button secondary" onClick={() => setOpen(true)}>{trigger}</button>{open && <div className="modal-backdrop" role="presentation"><section className="modal-card" role="dialog" aria-modal="true" aria-label="Edit employee"><div className="modal-head"><h2>Edit {employee?.name}</h2><button className="icon-button" onClick={() => setOpen(false)} aria-label="Close editor"><X size={16} /></button></div><div className="modal-body">{form}</div></section></div>}</>;
}
