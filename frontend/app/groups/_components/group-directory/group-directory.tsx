"use client";

import Link from "next/link";
import { ArrowRight, CircleAlert, Network, Plus, Search, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { type SubmitEvent, useState } from "react";
import { PaginationControls } from "@/components/shared";
import { Button, FormField, TextInput } from "@/components/ui";
import type { GroupDirectoryItem } from "@/lib/types";

export function GroupDirectory({
  initialGroups,
  canCreate = true,
  total,
  limit,
  offset,
  searchFilter,
}: {
  initialGroups: GroupDirectoryItem[];
  canCreate?: boolean;
  total: number;
  limit: number;
  offset: number;
  searchFilter: string;
}) {
  const router = useRouter();
  const groups = initialGroups;
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState(searchFilter);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const normalized = name.trim();

  async function createGroup() {
    if (!normalized) {
      setError("Enter a group name.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/backend/groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: normalized }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          result.error?.message ?? "The group could not be created.",
        );
      router.push(`/groups/${result.id}`);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create the group.");
    } finally {
      setSaving(false);
    }
  }

  function applySearch(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = search.trim();
    router.push(value ? `/groups?search=${encodeURIComponent(value)}` : "/groups");
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
          <Button
            onClick={() => {
              setCreating(true);
              setError("");
            }}
          >
            <Plus size={15} /> Create group
          </Button>
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
          <FormField label="Group name" htmlFor="new-group-name">
            <TextInput
              id="new-group-name"
              autoFocus
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setError("");
              }}
              placeholder="e.g. California employees"
            />
          </FormField>
          <div className="heading-actions">
            <Button
              variant="secondary"
              onClick={() => {
                setCreating(false);
                setName("");
              }}
            >
              Cancel
            </Button>
            <Button disabled={saving} onClick={createGroup}>
              {saving ? "Creating…" : "Create group"}
            </Button>
          </div>
          {error && (
            <div className="error-banner full-row">
              <CircleAlert size={13} />
              {error}
            </div>
          )}
        </section>
      )}
      <form className="toolbar" onSubmit={applySearch}>
        <div className="toolbar-left">
          <label className="search-box">
            <Search size={14} />
            <TextInput
              className="input"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search groups"
              aria-label="Search groups"
            />
          </label>
          <Button variant="secondary" type="submit">
            Apply
          </Button>
        </div>
        <div className="results-count">{total} groups</div>
      </form>
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
                  {group.member_count} members
                </span>
                <span>
                  {group.policy_count} attached {group.policy_count === 1 ? "policy" : "policies"}
                </span>
              </div>
            </div>
            <ArrowRight size={15} />
          </Link>
        ))}
      </div>
      <PaginationControls
        path="/groups"
        params={{ search: searchFilter }}
        total={total}
        limit={limit}
        offset={offset}
        itemLabel="groups"
      />
    </>
  );
}
