"use client";

import Link from "next/link";
import { Check, CircleAlert, FileKey2, Pencil, Trash2, Users, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { initials } from "@/lib/format";
import type { Employee, Group, Policy } from "@/lib/types";
import { EmployeeCombobox, PolicyCombobox } from "@/components/shared";
import { Badge, Button, Panel } from "@/components/ui";

export function GroupManager({
  group,
  initialMembers,
  initialPolicies,
  canManage = true,
}: {
  group: Group;
  initialMembers: Employee[];
  initialPolicies: Policy[];
  canManage?: boolean;
}) {
  const router = useRouter();
  const [name, setName] = useState(group.name);
  const [editingName, setEditingName] = useState(false);
  const [savedMembers, setSavedMembers] = useState(initialMembers);
  const [members, setMembers] = useState(initialMembers);
  const [savedPolicies, setSavedPolicies] = useState(initialPolicies);
  const [attachedPolicies, setAttachedPolicies] = useState(initialPolicies);
  const [employeePickerKey, setEmployeePickerKey] = useState(0);
  const [policyPickerKey, setPolicyPickerKey] = useState(0);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const membershipChanges = useMemo(() => {
    const savedIds = new Set(savedMembers.map((member) => member.id));
    const draftIds = new Set(members.map((member) => member.id));
    return {
      added: members.filter((member) => !savedIds.has(member.id)),
      removed: savedMembers.filter((member) => !draftIds.has(member.id)),
    };
  }, [members, savedMembers]);
  const membershipChangeCount = membershipChanges.added.length + membershipChanges.removed.length;
  const policyChanges = useMemo(() => {
    const savedIds = new Set(savedPolicies.map((policy) => policy.id));
    const draftIds = new Set(attachedPolicies.map((policy) => policy.id));
    return {
      added: attachedPolicies.filter((policy) => !savedIds.has(policy.id)),
      removed: savedPolicies.filter((policy) => !draftIds.has(policy.id)),
    };
  }, [attachedPolicies, savedPolicies]);
  const policyChangeCount = policyChanges.added.length + policyChanges.removed.length;

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
      if (!response.ok) throw new Error(result.error?.message ?? "The group could not be renamed.");
      setEditingName(false);
      setNotice("Group name updated.");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to rename the group.");
    } finally {
      setBusy("");
    }
  }

  async function submitMembershipChanges() {
    if (membershipChangeCount === 0) return;
    setBusy("membership");
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/backend/groups/${group.id}/employees`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          add_employee_ids: membershipChanges.added.map((employee) => employee.id),
          remove_employee_ids: membershipChanges.removed.map((employee) => employee.id),
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(result.error?.message ?? "The membership could not be updated.");
      setSavedMembers(members);
      setNotice(
        `Membership updated: ${membershipChanges.added.length} added and ${membershipChanges.removed.length} removed. Assignments were reconciled.`,
      );
      setEmployeePickerKey((current) => current + 1);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update membership.");
    } finally {
      setBusy("");
    }
  }

  async function submitPolicyChanges() {
    if (policyChangeCount === 0) return;
    setBusy("policy");
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/backend/groups/${group.id}/policies`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          add_policy_ids: policyChanges.added.map((policy) => policy.id),
          remove_policy_ids: policyChanges.removed.map((policy) => policy.id),
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(result.error?.message ?? "The policy attachments could not be updated.");
      setSavedPolicies(attachedPolicies);
      setNotice(
        `Policy attachments updated: ${policyChanges.added.length} added and ${policyChanges.removed.length} removed. Member assignments were reconciled.`,
      );
      setPolicyPickerKey((current) => current + 1);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update policy attachments.");
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
                {members.length} {members.length === 1 ? "employee" : "employees"} in this group
                {membershipChangeCount > 0 &&
                  ` · ${membershipChangeCount} unsaved ${membershipChangeCount === 1 ? "change" : "changes"}`}
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
                <EmployeeCombobox
                  key={employeePickerKey}
                  excludedEmployeeIds={members.map((member) => member.id)}
                  onChange={(employee) => {
                    if (!employee) return;
                    setMembers((current) =>
                      current.some((member) => member.id === employee.id)
                        ? current
                        : [...current, employee],
                    );
                    setEmployeePickerKey((current) => current + 1);
                    setError("");
                    setNotice("");
                  }}
                />
              </div>
            )}
            {canManage && (
              <div className="membership-draft-actions top">
                <span>
                  {membershipChangeCount === 0
                    ? "No unsaved membership changes"
                    : `${membershipChanges.added.length} to add · ${membershipChanges.removed.length} to remove`}
                </span>
                <div className="heading-actions">
                  <Button
                    variant="secondary"
                    disabled={membershipChangeCount === 0 || busy !== ""}
                    onClick={() => {
                      setMembers(savedMembers);
                      setEmployeePickerKey((current) => current + 1);
                    }}
                  >
                    Discard changes
                  </Button>
                  <Button
                    disabled={membershipChangeCount === 0 || busy !== ""}
                    onClick={submitMembershipChanges}
                  >
                    {busy === "membership" ? "Saving…" : "Save Changes"}
                  </Button>
                </div>
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
                      onClick={() => {
                        setMembers((current) =>
                          current.filter((member) => member.id !== employee.id),
                        );
                        setError("");
                        setNotice("");
                      }}
                      aria-label={`Remove ${employee.name} from draft`}
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
              <div className="panel-caption">
                Every member is evaluated against these policies
                {policyChangeCount > 0 &&
                  ` · ${policyChangeCount} unsaved ${policyChangeCount === 1 ? "change" : "changes"}`}
              </div>
            </div>
            <Badge>
              <FileKey2 size={11} />
              {attachedPolicies.length}
            </Badge>
          </div>
          <div className="panel-body">
            {canManage && (
              <div className="attach-row">
                <PolicyCombobox
                  key={policyPickerKey}
                  excludedPolicyIds={attachedPolicies.map((policy) => policy.id)}
                  onChange={(policy) => {
                    if (!policy) return;
                    setAttachedPolicies((current) =>
                      current.some((item) => item.id === policy.id)
                        ? current
                        : [...current, policy],
                    );
                    setPolicyPickerKey((current) => current + 1);
                    setError("");
                    setNotice("");
                  }}
                />
              </div>
            )}
            {canManage && (
              <div className="membership-draft-actions top">
                <span>
                  {policyChangeCount === 0
                    ? "No unsaved policy changes"
                    : `${policyChanges.added.length} to add · ${policyChanges.removed.length} to remove`}
                </span>
                <div className="heading-actions">
                  <Button
                    variant="secondary"
                    disabled={policyChangeCount === 0 || busy !== ""}
                    onClick={() => {
                      setAttachedPolicies(savedPolicies);
                      setPolicyPickerKey((current) => current + 1);
                    }}
                  >
                    Discard changes
                  </Button>
                  <Button
                    disabled={policyChangeCount === 0 || busy !== ""}
                    onClick={submitPolicyChanges}
                  >
                    {busy === "policy" ? "Saving…" : "Save Changes"}
                  </Button>
                </div>
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
                      className="remove-button danger"
                      disabled={busy !== ""}
                      onClick={() => {
                        setAttachedPolicies((current) =>
                          current.filter((item) => item.id !== policy.id),
                        );
                        setError("");
                        setNotice("");
                      }}
                      aria-label={`Remove ${policy.name} from draft`}
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
    </div>
  );
}
