"use client";

import Link from "next/link";
import { Check, CircleAlert, FileKey2, Pencil, Plus, Trash2, Users, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { formatEmployeeId, initials } from "@/lib/format";
import type { Employee, Group, Policy } from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";
import { Badge, Button, Panel } from "@/components/ui";

type MembershipChange = {
  action: "add" | "remove";
  employee: Employee;
  approvalToken: string | null;
  affectedCount: number;
};

export function GroupManager({
  group,
  initialMembers,
  initialPolicies,
  employees,
  policies,
  canManage = true,
}: {
  group: Group;
  initialMembers: Employee[];
  initialPolicies: Policy[];
  employees: Employee[];
  policies: Policy[];
  canManage?: boolean;
}) {
  const router = useRouter();
  const [name, setName] = useState(group.name);
  const [editingName, setEditingName] = useState(false);
  const [members, setMembers] = useState(initialMembers);
  const [attachedPolicies, setAttachedPolicies] = useState(initialPolicies);
  const [employeeId, setEmployeeId] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [pending, setPending] = useState<MembershipChange | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useModalAccessibility(Boolean(pending), () => setPending(null));
  const availableEmployees = useMemo(
    () => employees.filter((employee) => !members.some((member) => member.id === employee.id)),
    [employees, members],
  );
  const availablePolicies = useMemo(
    () =>
      policies.filter(
        (policy) =>
          policy.status === "active" && !attachedPolicies.some((item) => item.id === policy.id),
      ),
    [policies, attachedPolicies],
  );

  async function rename() {
    const next = name.trim();
    if (!next) {
      setError("Group name cannot be empty.");
      return;
    }
    setBusy("rename");
    setError("");
    try {
      const response = await fetch(`/api/backend/groups/${group.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: next }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          result.error?.message ?? result.detail ?? "The group could not be renamed.",
        );
      setEditingName(false);
      setNotice("Group name updated.");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to rename the group.");
    } finally {
      setBusy("");
    }
  }

  async function previewMembership(action: "add" | "remove", employee: Employee) {
    setBusy(`preview-${employee.id}`);
    setError("");
    setNotice("");
    const change = {
      type: "group_membership_change",
      action,
      group_id: group.id,
      employee_id: employee.id,
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
            "The membership impact could not be calculated.",
        );
      setPending({
        action,
        employee,
        approvalToken: result.approval?.token ?? null,
        affectedCount: result.changes?.[0]
          ? result.changes[0].added.length +
            result.changes[0].removed.length +
            result.changes[0].changed.length
          : result.affected_employee_count,
      });
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to preview the membership change.",
      );
    } finally {
      setBusy("");
    }
  }

  async function confirmMembership() {
    if (!pending) return;
    setBusy("membership");
    setError("");
    const change = {
      type: "group_membership_change",
      action: pending.action,
      group_id: group.id,
      employee_id: pending.employee.id,
    };
    try {
      const endpoint = pending.approvalToken
        ? "/api/backend/change-executions"
        : `/api/backend/groups/${group.id}/employees/${pending.employee.id}`;
      const response = await fetch(endpoint, {
        method: pending.approvalToken ? "POST" : pending.action === "add" ? "POST" : "DELETE",
        headers: pending.approvalToken ? { "Content-Type": "application/json" } : undefined,
        body: pending.approvalToken
          ? JSON.stringify({ approval_token: pending.approvalToken, change })
          : undefined,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          result.error?.message ?? result.detail ?? "The membership could not be updated.",
        );
      setMembers((current) =>
        pending.action === "add"
          ? [...current, pending.employee]
          : current.filter((item) => item.id !== pending.employee.id),
      );
      setNotice(
        `${pending.employee.name} ${pending.action === "add" ? "added to" : "removed from"} ${name}. Assignments were reconciled.`,
      );
      setEmployeeId("");
      setPending(null);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update membership.");
    } finally {
      setBusy("");
    }
  }

  async function attachPolicy() {
    const policy = availablePolicies.find((item) => item.id === Number(policyId));
    if (!policy) return;
    setBusy("policy");
    setError("");
    try {
      const response = await fetch(`/api/backend/groups/${group.id}/policies/${policy.id}`, {
        method: "POST",
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          result.error?.message ?? result.detail ?? "The policy could not be attached.",
        );
      setAttachedPolicies((current) => [...current, policy]);
      setPolicyId("");
      setNotice(`${policy.name} attached. Member assignments were reconciled.`);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to attach the policy.");
    } finally {
      setBusy("");
    }
  }

  async function detachPolicy(policy: Policy) {
    setBusy(`policy-${policy.id}`);
    setError("");
    try {
      const response = await fetch(`/api/backend/groups/${group.id}/policies/${policy.id}`, {
        method: "DELETE",
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          result.error?.message ?? result.detail ?? "The policy could not be detached.",
        );
      setAttachedPolicies((current) => current.filter((item) => item.id !== policy.id));
      setNotice(`${policy.name} detached. Member assignments were reconciled.`);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to detach the policy.");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="section-stack">
      {(error || notice) && (
        <div
          className={error ? "error-banner" : "success-banner"}
          role={error ? "alert" : "status"}
        >
          {error ? <CircleAlert size={14} /> : <Check size={14} />}
          {error || notice}
        </div>
      )}
      <Panel>
        <div className="panel-header">
          <div>
            {editingName ? (
              <div className="heading-actions">
                <input
                  className="input"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  aria-label="Group name"
                />
                <Button onClick={rename} disabled={busy === "rename"}>
                  <Check size={14} /> Save
                </Button>
                <button
                  className="icon-button"
                  onClick={() => {
                    setEditingName(false);
                    setName(group.name);
                  }}
                  aria-label="Cancel rename"
                >
                  <X size={14} />
                </button>
              </div>
            ) : (
              <>
                <h2 className="panel-title">{name}</h2>
                <div className="panel-caption">Explicit group · changes reconcile immediately</div>
              </>
            )}
          </div>
          {canManage && !editingName && (
            <Button variant="secondary" size="small" onClick={() => setEditingName(true)}>
              <Pencil size={13} /> Rename
            </Button>
          )}
        </div>
      </Panel>
      <div className="detail-grid">
        <Panel>
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Members</h2>
              <div className="panel-caption">
                {members.length} {members.length === 1 ? "employee inherits" : "employees inherit"}{" "}
                attached policies
              </div>
            </div>
            <Badge tone="accent">
              <Users size={11} />
              {members.length}
            </Badge>
          </div>
          <div className="panel-body">
            {canManage && (
              <div className="attach-row">
                <select
                  className="select"
                  value={employeeId}
                  onChange={(event) => setEmployeeId(event.target.value)}
                >
                  <option value="">Select an employee</option>
                  {availableEmployees.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.name} · {employee.department} · {formatEmployeeId(employee.id)}
                    </option>
                  ))}
                </select>
                <Button
                  disabled={!employeeId || busy !== ""}
                  onClick={() => {
                    const employee = availableEmployees.find(
                      (item) => item.id === Number(employeeId),
                    );
                    if (employee) void previewMembership("add", employee);
                  }}
                >
                  <Plus size={14} /> Review add
                </Button>
              </div>
            )}
            <div className="member-list">
              {members.map((employee) => (
                <div className="member-row" key={employee.id}>
                  <Link className="person-cell" href={`/employees/${employee.id}`}>
                    <span className="avatar">{initials(employee.name)}</span>
                    <span>
                      <span className="primary-cell">{employee.name}</span>
                      <span className="secondary-cell">
                        {employee.department} · {employee.state_label}
                      </span>
                    </span>
                  </Link>
                  {canManage && (
                    <button
                      className="remove-button danger"
                      disabled={busy !== ""}
                      onClick={() => previewMembership("remove", employee)}
                      aria-label={`Remove ${employee.name}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
              {members.length === 0 && <div className="empty-state compact">No members yet.</div>}
            </div>
          </div>
        </Panel>
        <Panel>
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Attached policies</h2>
              <div className="panel-caption">Every member is evaluated against these policies</div>
            </div>
            <Badge>
              <FileKey2 size={11} />
              {attachedPolicies.length}
            </Badge>
          </div>
          <div className="panel-body">
            {canManage && (
              <div className="attach-row">
                <select
                  className="select"
                  value={policyId}
                  onChange={(event) => setPolicyId(event.target.value)}
                >
                  <option value="">Select an active policy</option>
                  {availablePolicies.map((policy) => (
                    <option key={policy.id} value={policy.id}>
                      {policy.name}
                    </option>
                  ))}
                </select>
                <Button disabled={!policyId || busy !== ""} onClick={attachPolicy}>
                  <Plus size={14} /> Attach
                </Button>
              </div>
            )}
            <div className="member-list">
              {attachedPolicies.map((policy) => (
                <div className="member-row" key={policy.id}>
                  <Link href={`/policies/${policy.id}`}>
                    <span className="primary-cell">{policy.name}</span>
                    <span className="secondary-cell">
                      Priority {policy.versions.at(-1)?.priority ?? "—"} · {policy.status}
                    </span>
                  </Link>
                  {canManage && (
                    <button
                      className="remove-button"
                      disabled={busy !== ""}
                      onClick={() => detachPolicy(policy)}
                      aria-label={`Detach ${policy.name}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
              {attachedPolicies.length === 0 && (
                <div className="empty-state compact">No policies attached.</div>
              )}
            </div>
          </div>
        </Panel>
      </div>
      {pending && (
        <div className="modal-backdrop" role="presentation">
          <section
            className="confirm-card"
            role="dialog"
            aria-modal="true"
            aria-label="Confirm membership change"
          >
            <div className="confirm-icon">
              <Users size={18} />
            </div>
            <h2>
              {pending.action === "add" ? "Add" : "Remove"} {pending.employee.name}?
            </h2>
            <p>
              This membership change will update {pending.affectedCount} assignment{" "}
              {pending.affectedCount === 1 ? "value" : "values"}. The policy engine will record the
              reason and reconcile the employee immediately.
            </p>
            <div className="heading-actions">
              <Button variant="secondary" onClick={() => setPending(null)}>
                Cancel
              </Button>
              <Button disabled={busy === "membership"} onClick={confirmMembership}>
                {busy === "membership" ? "Applying…" : "Confirm and reconcile"}
              </Button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
