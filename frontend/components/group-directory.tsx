"use client";

import Link from "next/link";
import { ArrowRight, CircleAlert, Network, Plus, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { Group } from "@/lib/types";

type GroupRow = Group & { memberCount: number; policyCount: number };

export function GroupDirectory({
  initialGroups,
  apiConfigured,
  canCreate = true,
}: {
  initialGroups: GroupRow[];
  apiConfigured: boolean;
  canCreate?: boolean;
}) {
  const router = useRouter();
  const [groups, setGroups] = useState(initialGroups);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const normalized = name.trim();
  const duplicate = useMemo(
    () => groups.some((group) => group.name.toLowerCase() === normalized.toLowerCase()),
    [groups, normalized],
  );

  async function createGroup() {
    if (!normalized || duplicate) {
      setError(duplicate ? "A group with this name already exists." : "Enter a group name.");
      return;
    }
    setSaving(true);
    setError("");
    if (!apiConfigured) {
      const group = {
        id: Math.max(...groups.map((item) => item.id), 0) + 1,
        name: normalized,
        memberCount: 0,
        policyCount: 0,
      };
      setGroups((current) => [...current, group]);
      setName("");
      setCreating(false);
      setSaving(false);
      return;
    }
    try {
      const response = await fetch("/api/backend/groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: normalized }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          result.error?.message ?? result.detail ?? "The group could not be created.",
        );
      router.push(`/groups/${result.id}`);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create the group.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Collections</p>
          <h1>Groups</h1>
          <p className="page-subtitle">
            Manage explicit employee populations and the policies every member inherits.
          </p>
        </div>
        {canCreate && (
          <button
            className="button"
            onClick={() => {
              setCreating(true);
              setError("");
            }}
          >
            <Plus size={15} /> Create group
          </button>
        )}
      </div>
      {creating && (
        <section className="inline-create">
          <div>
            <div className="form-section-title">Create a group</div>
            <div className="form-section-description">
              Start with a clear population name. Members and policies are added on the next screen.
            </div>
          </div>
          <label className="field">
            <span className="field-label">Group name</span>
            <input
              className="input"
              autoFocus
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setError("");
              }}
              placeholder="e.g. California employees"
            />
          </label>
          <div className="heading-actions">
            <button
              className="button secondary"
              onClick={() => {
                setCreating(false);
                setName("");
              }}
            >
              Cancel
            </button>
            <button className="button" disabled={saving} onClick={createGroup}>
              {saving ? "Creating…" : "Create group"}
            </button>
          </div>
          {error && (
            <div className="error-banner full-row">
              <CircleAlert size={13} />
              {error}
            </div>
          )}
        </section>
      )}
      <div className="management-grid">
        {groups.map((group) => (
          <Link className="management-card" href={`/groups/${group.id}`} key={group.id}>
            <div className="management-card-icon">
              <Network size={17} />
            </div>
            <div className="management-card-main">
              <div className="management-card-title">{group.name}</div>
              <div className="management-card-meta">
                <span>
                  <Users size={12} />
                  {group.memberCount} members
                </span>
                <span>
                  {group.policyCount} attached {group.policyCount === 1 ? "policy" : "policies"}
                </span>
              </div>
            </div>
            <ArrowRight size={15} />
          </Link>
        ))}
      </div>
    </>
  );
}
