"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Check,
  CircleAlert,
  KeyRound,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { type SubmitEvent, useEffect, useId, useMemo, useState } from "react";
import {
  AppliedFilterRow,
  DirectoryResultsStatus,
  PaginationControls,
  useFilterNavigation,
} from "@/components/shared";
import {
  Badge,
  Button,
  ConfirmDialog,
  DataTable,
  Panel,
  SelectInput,
  TextInput,
} from "@/components/ui";
import { formatEmployeeId, titleCase } from "@/lib/format";
import type {
  AssignmentFieldScopeOption,
  CollectionPage,
  EmployeeCandidate,
  Permission,
  Role,
  RoleCandidate,
  RoleDirectoryItem,
  RoleSummary,
  UserDirectoryItem,
} from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";

type AccessTab = "users" | "roles";

type Props = {
  tab: AccessTab;
  userPage?: CollectionPage<UserDirectoryItem>;
  rolePage?: CollectionPage<RoleDirectoryItem>;
  filters: { search: string; status: string; roleId?: number };
  initialRoleFilter: RoleCandidate | null;
  canManage: boolean;
  canReadEmployees: boolean;
  mfaEnabled: boolean;
};

const employeeScopeLabels: Record<Role["employee_scope"], string> = {
  all: "All employees",
  reporting_tree: "Linked employee and reporting tree",
  self: "Linked employee only",
  none: "No employees",
};

const assignmentFieldScopeLabels: Record<Role["assignment_field_scope"], string> = {
  all: "All assignment fields",
  selected: "Selected assignment fields",
  none: "No assignment fields",
};

export function AccessManager({
  tab,
  userPage,
  rolePage,
  filters,
  initialRoleFilter,
  canManage,
  canReadEmployees,
  mfaEnabled,
}: Props) {
  const router = useRouter();
  const [editingRoleId, setEditingRoleId] = useState<number | null | undefined>(undefined);
  const [editingUser, setEditingUser] = useState<UserDirectoryItem | null | undefined>(undefined);
  const [message, setMessage] = useState<{ type: "error" | "success"; text: string } | null>(null);

  function completed(text: string) {
    setMessage({ type: "success", text });
    router.refresh();
    window.setTimeout(() => setMessage(null), 3500);
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Authorization</p>
          <h1>Access control</h1>
          <p className="page-subtitle">
            Create reusable roles, choose their exact permissions, and assign those roles to human
            users.
          </p>
        </div>
        {canManage && (
          <Button onClick={() => (tab === "users" ? setEditingUser(null) : setEditingRoleId(null))}>
            <Plus size={15} /> {tab === "users" ? "Create user" : "Create role"}
          </Button>
        )}
      </div>
      {message && (
        <div
          className={message.type === "error" ? "error-banner" : "success-banner"}
          role={message.type === "error" ? "alert" : "status"}
        >
          {message.type === "error" ? <CircleAlert size={14} /> : <Check size={14} />}
          {message.text}
        </div>
      )}
      <nav className="segmented access-tabs" aria-label="Access control sections">
        <Link className={tab === "users" ? "active" : ""} href="/access?tab=users">
          <Users size={14} /> Users
        </Link>
        <Link className={tab === "roles" ? "active" : ""} href="/access?tab=roles">
          <ShieldCheck size={14} /> Roles
        </Link>
      </nav>
      {tab === "users" && userPage ? (
        <UsersPanel
          key={`users:${filters.search}:${filters.status}:${filters.roleId ?? ""}`}
          page={userPage}
          filters={filters}
          initialRoleFilter={initialRoleFilter}
          canManage={canManage}
          onEdit={setEditingUser}
          onError={(text) => setMessage({ type: "error", text })}
          onComplete={completed}
        />
      ) : tab === "roles" && rolePage ? (
        <RolesPanel
          key={`roles:${filters.search}`}
          page={rolePage}
          searchFilter={filters.search}
          canManage={canManage}
          onEdit={setEditingRoleId}
          onError={(text) => setMessage({ type: "error", text })}
          onComplete={completed}
        />
      ) : null}
      {editingRoleId !== undefined && (
        <RoleFormLoader
          roleId={editingRoleId}
          mfaEnabled={mfaEnabled}
          onClose={() => setEditingRoleId(undefined)}
          onSaved={(created) => {
            setEditingRoleId(undefined);
            completed(created ? "Role created." : "Role updated.");
          }}
        />
      )}
      {editingUser !== undefined && (
        <UserForm
          user={editingUser}
          canReadEmployees={canReadEmployees}
          mfaEnabled={mfaEnabled}
          onClose={() => setEditingUser(undefined)}
          onSaved={(created) => {
            setEditingUser(undefined);
            completed(created ? "User created with a temporary password." : "User updated.");
          }}
        />
      )}
    </>
  );
}

function UsersPanel({
  page,
  filters,
  initialRoleFilter,
  canManage,
  onEdit,
  onError,
  onComplete,
}: {
  page: CollectionPage<UserDirectoryItem>;
  filters: Props["filters"];
  initialRoleFilter: RoleCandidate | null;
  canManage: boolean;
  onEdit(user: UserDirectoryItem): void;
  onError(text: string): void;
  onComplete(text: string): void;
}) {
  const appliedFromServer = useMemo(
    () => ({ search: filters.search, status: filters.status, role: initialRoleFilter }),
    [filters.search, filters.status, initialRoleFilter],
  );
  const navigation = useFilterNavigation(appliedFromServer);
  const [search, setSearch] = useState(filters.search);
  const [status, setStatus] = useState(filters.status);
  const [role, setRole] = useState<RoleCandidate | null>(initialRoleFilter);
  const [pendingDisable, setPendingDisable] = useState<UserDirectoryItem | null>(null);
  const [disabling, setDisabling] = useState(false);
  const applied = navigation.filters;
  const activeFilters = [
    applied.search ? { key: "search", label: `Search: ${applied.search}` } : null,
    applied.status ? { key: "status", label: `Status: ${titleCase(applied.status)}` } : null,
    applied.role ? { key: "role", label: `Role: ${applied.role.name}` } : null,
  ].filter((item): item is { key: string; label: string } => Boolean(item));

  function applyFilters(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = new URLSearchParams({ tab: "users" });
    if (search.trim()) query.set("search", search.trim());
    if (status) query.set("status", status);
    if (role) query.set("role_id", String(role.id));
    navigation.navigate(`/access?${query}`, {
      search: search.trim(),
      status,
      role,
    });
  }

  function clearFilters() {
    setSearch("");
    setStatus("");
    setRole(null);
    navigation.navigate("/access?tab=users", { search: "", status: "", role: null });
  }

  function removeFilter(key: string) {
    const next = {
      search: key === "search" ? "" : applied.search,
      status: key === "status" ? "" : applied.status,
      role: key === "role" ? null : applied.role,
    };
    if (key === "search") setSearch("");
    if (key === "status") setStatus("");
    if (key === "role") setRole(null);
    const query = new URLSearchParams({ tab: "users" });
    if (next.search) query.set("search", next.search);
    if (next.status) query.set("status", next.status);
    if (next.role) query.set("role_id", String(next.role.id));
    navigation.navigate(`/access?${query}`, next);
  }

  async function disable(user: UserDirectoryItem) {
    setDisabling(true);
    try {
      const response = await fetch(`/api/backend/users/${user.id}`, { method: "DELETE" });
      if (!response.ok) return onError(await errorMessage(response));
      setPendingDisable(null);
      onComplete(`${user.name} was disabled.`);
    } finally {
      setDisabling(false);
    }
  }

  return (
    <>
      <section className="directory-controls" aria-label="User directory controls">
        <div className="directory-controls-head">
          <div>
            <span className="section-kicker">User directory</span>
            <strong>{page.total} users</strong>
          </div>
          <DirectoryResultsStatus pending={navigation.isPending}>
            {activeFilters.length
              ? `${activeFilters.length} active ${activeFilters.length === 1 ? "filter" : "filters"}`
              : "Showing all users"}
          </DirectoryResultsStatus>
        </div>
        <form className="toolbar" onSubmit={applyFilters}>
          <div className="toolbar-left">
            <label className="search-box">
              <Search size={14} />
              <TextInput
                className="input"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search users by name or email"
                aria-label="Search users"
              />
            </label>
            <SelectInput
              className="filter-select"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              aria-label="Filter users by status"
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="disabled">Disabled</option>
            </SelectInput>
            <RoleCombobox selected={role} onChange={setRole} placeholder="Filter by role" />
            <Button variant="secondary" type="submit">
              Apply filters
            </Button>
          </div>
        </form>
        <AppliedFilterRow filters={activeFilters} onRemove={removeFilter} onClear={clearFilters} />
      </section>
      <Panel
        as="div"
        className="access-table results-region"
        clipped
        aria-busy={navigation.isPending}
      >
        {page.items.length ? (
          <DataTable>
            <thead>
              <tr>
                <th>User</th>
                <th>Employee link</th>
                <th>Roles</th>
                <th>Effective permissions</th>
                <th>Status</th>
                {canManage && (
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {page.items.map((user) => (
                <tr
                  className={
                    user.is_root || user.has_all_permissions ? "access-privileged-row" : undefined
                  }
                  key={user.id}
                >
                  <td>
                    <span className="primary-cell">{user.name}</span>
                    <span className="secondary-cell">{user.email}</span>
                  </td>
                  <td>
                    {user.employee_link_hidden ? (
                      <span className="secondary-cell">Outside your employee scope</span>
                    ) : user.employee ? (
                      <>
                        <span className="primary-cell">{user.employee.name}</span>
                        <span className="secondary-cell">
                          {user.employee.department} · {formatEmployeeId(user.employee.id)}
                        </span>
                      </>
                    ) : (
                      <span className="secondary-cell">Not linked</span>
                    )}
                  </td>
                  <td>
                    {user.is_root ? (
                      <Badge tone="accent">Root</Badge>
                    ) : (
                      user.roles.map((item) => <Badge key={item.id}>{item.name}</Badge>)
                    )}
                  </td>
                  <td>
                    {user.has_all_permissions ? (
                      <Badge tone="accent">All permissions</Badge>
                    ) : (
                      <span className="primary-cell">
                        {user.effective_permission_count} permissions
                      </span>
                    )}
                    {user.password_change_required && (
                      <span className="secondary-cell">Password change required</span>
                    )}
                  </td>
                  <td>
                    <Badge tone={user.status === "active" ? "success" : "neutral"}>
                      {user.status}
                    </Badge>
                  </td>
                  {canManage && (
                    <td>
                      <div className="row-actions">
                        {!user.is_root && (
                          <>
                            <button
                              className="icon-button"
                              aria-label={`Edit ${user.name}`}
                              onClick={() => onEdit(user)}
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              className="icon-button danger-button"
                              aria-label={`Disable ${user.name}`}
                              disabled={user.status === "disabled"}
                              onClick={() => setPendingDisable(user)}
                            >
                              <Trash2 size={14} />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </DataTable>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">
              <Users size={18} />
            </div>
            <strong>No users match</strong>
            <span>Try another search or clear the filters.</span>
            <button className="text-button" onClick={clearFilters}>
              <X size={13} /> Clear filters
            </button>
          </div>
        )}
        <PaginationControls
          path="/access"
          params={{
            tab: "users",
            search: filters.search,
            status: filters.status,
            role_id: filters.roleId ? String(filters.roleId) : undefined,
          }}
          total={page.total}
          limit={page.limit}
          offset={page.offset}
          itemLabel="users"
        />
      </Panel>
      <ConfirmDialog
        open={Boolean(pendingDisable)}
        title={`Disable ${pendingDisable?.name ?? "user"}?`}
        description="This immediately ends every active session for the user. Their audit history remains available and an administrator can restore access later."
        confirmLabel="Disable user"
        busy={disabling}
        onCancel={() => setPendingDisable(null)}
        onConfirm={() => pendingDisable && void disable(pendingDisable)}
      />
    </>
  );
}

function RolesPanel({
  page,
  searchFilter,
  canManage,
  onEdit,
  onError,
  onComplete,
}: {
  page: CollectionPage<RoleDirectoryItem>;
  searchFilter: string;
  canManage: boolean;
  onEdit(id: number): void;
  onError(text: string): void;
  onComplete(text: string): void;
}) {
  const appliedFromServer = useMemo(() => ({ search: searchFilter }), [searchFilter]);
  const navigation = useFilterNavigation(appliedFromServer);
  const [search, setSearch] = useState(searchFilter);
  const [pendingDelete, setPendingDelete] = useState<RoleDirectoryItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const activeFilters = navigation.filters.search
    ? [{ key: "search", label: `Search: ${navigation.filters.search}` }]
    : [];

  function applySearch(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = new URLSearchParams({ tab: "roles" });
    if (search.trim()) query.set("search", search.trim());
    navigation.navigate(`/access?${query}`, { search: search.trim() });
  }

  function clearSearch() {
    setSearch("");
    navigation.navigate("/access?tab=roles", { search: "" });
  }

  async function remove(role: RoleDirectoryItem) {
    setDeleting(true);
    try {
      const response = await fetch(`/api/backend/roles/${role.id}`, { method: "DELETE" });
      if (!response.ok) return onError(await errorMessage(response));
      setPendingDelete(null);
      onComplete(`${role.name} was deleted.`);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <section className="directory-controls" aria-label="Role directory controls">
        <div className="directory-controls-head">
          <div>
            <span className="section-kicker">Role directory</span>
            <strong>{page.total} roles</strong>
          </div>
          <DirectoryResultsStatus pending={navigation.isPending}>
            {activeFilters.length ? "1 active filter" : "Showing all roles"}
          </DirectoryResultsStatus>
        </div>
        <form className="toolbar" onSubmit={applySearch}>
          <div className="toolbar-left">
            <label className="search-box">
              <Search size={14} />
              <TextInput
                className="input"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search roles"
                aria-label="Search roles"
              />
            </label>
            <Button variant="secondary" type="submit">
              Apply filters
            </Button>
          </div>
        </form>
        <AppliedFilterRow filters={activeFilters} onRemove={clearSearch} onClear={clearSearch} />
      </section>
      <div className="role-grid results-region" aria-busy={navigation.isPending}>
        {page.items.map((role) => {
          const broadAccess =
            role.employee_scope === "all" || role.assignment_field_scope === "all";
          return (
            <Panel
              as="article"
              className={`role-card${broadAccess ? " broad-access" : ""}`}
              key={role.id}
            >
              <div className="role-card-head">
                <div className="role-icon">
                  <ShieldCheck size={16} />
                </div>
                {canManage && (
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      aria-label={`Edit ${role.name}`}
                      onClick={() => onEdit(role.id)}
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      className="icon-button danger-button"
                      aria-label={`Delete ${role.name}`}
                      disabled={role.user_count > 0}
                      onClick={() => setPendingDelete(role)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>
              <h2>{role.name}</h2>
              {broadAccess && <Badge tone="accent">Broad access</Badge>}
              <p>{role.description || "No description provided."}</p>
              <div className="role-card-meta">
                <span>{role.permission_count} permissions</span>
                <span>{role.user_count} users</span>
              </div>
              <div className="permission-chip-list">
                <Badge tone="accent">{employeeScopeLabels[role.employee_scope]}</Badge>
                <Badge tone="accent">
                  {role.assignment_field_scope === "selected"
                    ? `${role.assignment_field_count} assignment fields`
                    : assignmentFieldScopeLabels[role.assignment_field_scope]}
                </Badge>
                {role.permission_preview.map((permission) => (
                  <Badge key={permission}>{permission}</Badge>
                ))}
                {role.permission_count > role.permission_preview.length && (
                  <Badge tone="accent">
                    +{role.permission_count - role.permission_preview.length}
                  </Badge>
                )}
              </div>
            </Panel>
          );
        })}
        {page.items.length === 0 && (
          <Panel as="div" className="empty-state">
            <div className="empty-icon">
              <ShieldCheck size={18} />
            </div>
            <strong>No roles match</strong>
            <span>Try another search or create a new role.</span>
          </Panel>
        )}
      </div>
      <PaginationControls
        path="/access"
        params={{ tab: "roles", search: searchFilter }}
        total={page.total}
        limit={page.limit}
        offset={page.offset}
        itemLabel="roles"
      />
      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title={`Delete ${pendingDelete?.name ?? "role"}?`}
        description="This permanently removes the unused role. Existing audit records remain available, but the role cannot be recovered."
        confirmLabel="Delete role"
        busy={deleting}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && void remove(pendingDelete)}
      />
    </>
  );
}

function RoleFormLoader({
  roleId,
  mfaEnabled,
  onClose,
  onSaved,
}: {
  roleId: number | null;
  mfaEnabled: boolean;
  onClose(): void;
  onSaved(created: boolean): void;
}) {
  useModalAccessibility(true, onClose);
  const [data, setData] = useState<{
    role: Role | null;
    permissions: Permission[];
    assignmentFields: AssignmentFieldScopeOption[];
  } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const [roleResponse, permissionsResponse, fieldsResponse] = await Promise.all([
          roleId === null
            ? Promise.resolve(null)
            : fetch(`/api/backend/roles/${roleId}`, { signal: controller.signal }),
          fetch("/api/backend/authorization/permissions?limit=500", { signal: controller.signal }),
          fetch("/api/backend/authorization/assignment-fields", { signal: controller.signal }),
        ]);
        if (roleResponse && !roleResponse.ok) throw new Error(await errorMessage(roleResponse));
        if (!permissionsResponse.ok) throw new Error(await errorMessage(permissionsResponse));
        if (!fieldsResponse.ok) throw new Error(await errorMessage(fieldsResponse));
        setData({
          role: roleResponse ? await roleResponse.json() : null,
          permissions: await permissionsResponse.json(),
          assignmentFields: await fieldsResponse.json(),
        });
      } catch (reason) {
        if ((reason as Error).name !== "AbortError") {
          setError(
            reason instanceof Error ? reason.message : "Role configuration could not be loaded.",
          );
        }
      }
    }
    load();
    return () => controller.abort();
  }, [roleId]);

  if (data) {
    return <RoleForm {...data} mfaEnabled={mfaEnabled} onClose={onClose} onSaved={onSaved} />;
  }
  return (
    <div className="modal-backdrop">
      <div className="form-dialog access-form-dialog" role="dialog" aria-modal="true">
        <div className="modal-head">
          <div>
            <p className="eyebrow">Permission bundle</p>
            <h2>Loading role…</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">
          {error ? (
            <div className="error-banner" role="alert">
              <CircleAlert size={14} />
              {error}
            </div>
          ) : (
            <p className="form-hint">Loading permissions and assignment fields…</p>
          )}
        </div>
      </div>
    </div>
  );
}

function RoleForm({
  role,
  permissions,
  assignmentFields,
  mfaEnabled,
  onClose,
  onSaved,
}: {
  role: Role | null;
  permissions: Permission[];
  assignmentFields: AssignmentFieldScopeOption[];
  mfaEnabled: boolean;
  onClose(): void;
  onSaved(created: boolean): void;
}) {
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [employeeScope, setEmployeeScope] = useState<Role["employee_scope"]>(
    role?.employee_scope ?? "none",
  );
  const [assignmentFieldScope, setAssignmentFieldScope] = useState<Role["assignment_field_scope"]>(
    role?.assignment_field_scope ?? "none",
  );
  const [assignmentFieldIds, setAssignmentFieldIds] = useState<number[]>(
    role?.assignment_field_ids ?? [],
  );
  const [selected, setSelected] = useState<string[]>(role?.permissions ?? []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [passwordInvalid, setPasswordInvalid] = useState(false);
  const [mfaInvalid, setMfaInvalid] = useState(false);
  const groups = useMemo(() => [...new Set(permissions.map((item) => item.group))], [permissions]);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const missingPassword = currentPassword.length === 0;
    const missingMfaCode = mfaEnabled && mfaCode.length === 0;
    setPasswordInvalid(missingPassword);
    setMfaInvalid(missingMfaCode);
    if (missingPassword || missingMfaCode) return;
    setBusy(true);
    try {
      const authenticationFailure = await reauthenticateSensitiveAction(currentPassword, mfaCode);
      if (authenticationFailure) {
        setError(authenticationFailure.message);
        setPasswordInvalid(authenticationFailure.code === "invalid_current_password");
        setMfaInvalid(authenticationFailure.code === "invalid_mfa_code");
        return;
      }
      const response = await fetch(`/api/backend/roles${role ? `/${role.id}` : ""}`, {
        method: role ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          description,
          permissions: selected,
          employee_scope: employeeScope,
          assignment_field_scope: assignmentFieldScope,
          assignment_field_ids: assignmentFieldScope === "selected" ? assignmentFieldIds : [],
        }),
      });
      if (!response.ok) return setError(await errorMessage(response));
      onSaved(role === null);
    } catch {
      setError("The role could not be saved. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function toggle(value: string) {
    setSelected((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    );
  }

  function toggleAssignmentField(id: number) {
    setAssignmentFieldIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  return (
    <div className="modal-backdrop">
      <form className="form-dialog access-form-dialog" onSubmit={submit}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">Permission bundle</p>
            <h2>{role ? `Edit ${role.name}` : "Create a role"}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">
          <div className="field-grid">
            <label className="field">
              <span className="field-label">Role name</span>
              <input
                className="input"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">Employee visibility</span>
              <select
                className="select"
                value={employeeScope}
                onChange={(event) => setEmployeeScope(event.target.value as Role["employee_scope"])}
              >
                <option value="none">No employees</option>
                <option value="self">Linked employee only</option>
                <option value="reporting_tree">Linked employee and reporting tree</option>
                <option value="all">All employees</option>
              </select>
            </label>
            <label className="field">
              <span className="field-label">Assignment field access</span>
              <select
                className="select"
                value={assignmentFieldScope}
                onChange={(event) =>
                  setAssignmentFieldScope(event.target.value as Role["assignment_field_scope"])
                }
              >
                <option value="none">No assignment fields</option>
                <option value="selected">Selected assignment fields</option>
                <option value="all">All assignment fields</option>
              </select>
            </label>
            <label className="field full">
              <span className="field-label">Description</span>
              <textarea
                className="textarea"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
          </div>
          <p className="form-hint">
            Employee visibility and assignment field access independently limit the data this role
            can reach.
          </p>
          {assignmentFieldScope === "selected" && (
            <fieldset className="role-options">
              <legend>Allowed assignment fields</legend>
              {assignmentFields.map((field) => (
                <label className="permission-option" key={field.id}>
                  <input
                    type="checkbox"
                    checked={assignmentFieldIds.includes(field.id)}
                    onChange={() => toggleAssignmentField(field.id)}
                  />
                  <span>
                    <strong>{field.name}</strong>
                    <small>
                      {field.cardinality === "one"
                        ? "One value per employee"
                        : "Multiple values per employee"}
                    </small>
                  </span>
                </label>
              ))}
            </fieldset>
          )}
          <div className="permission-groups">
            {groups.map((group) => (
              <fieldset key={group}>
                <legend>{group}</legend>
                {permissions
                  .filter((item) => item.group === group)
                  .map((permission) => (
                    <label className="permission-option" key={permission.name}>
                      <input
                        type="checkbox"
                        checked={selected.includes(permission.name)}
                        onChange={() => toggle(permission.name)}
                      />
                      <span>
                        <strong>{permission.label}</strong>
                        <small>{permission.description}</small>
                      </span>
                    </label>
                  ))}
              </fieldset>
            ))}
          </div>
        </div>
        <SensitiveConfirmation
          password={currentPassword}
          mfaCode={mfaCode}
          mfaEnabled={mfaEnabled}
          passwordInvalid={passwordInvalid}
          mfaInvalid={mfaInvalid}
          onPasswordChange={(value) => {
            setCurrentPassword(value);
            setPasswordInvalid(false);
            setError("");
          }}
          onMfaCodeChange={(value) => {
            setMfaCode(value);
            setMfaInvalid(false);
            setError("");
          }}
        />
        {error && (
          <div className="error-banner dialog-error" role="alert">
            <CircleAlert size={14} />
            <span>{error}</span>
          </div>
        )}
        <div className="form-footer">
          <span className="form-hint">
            {selected.length} permissions selected · {employeeScopeLabels[employeeScope]} ·{" "}
            {assignmentFieldScope === "selected"
              ? `${assignmentFieldIds.length} assignment fields`
              : assignmentFieldScopeLabels[assignmentFieldScope]}
          </span>
          <div className="heading-actions">
            <Button variant="secondary" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save role"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}

function UserForm({
  user,
  canReadEmployees,
  mfaEnabled,
  onClose,
  onSaved,
}: {
  user: UserDirectoryItem | null;
  canReadEmployees: boolean;
  mfaEnabled: boolean;
  onClose(): void;
  onSaved(created: boolean): void;
}) {
  useModalAccessibility(true, onClose);
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<UserDirectoryItem["status"]>(user?.status ?? "active");
  const [selectedRoles, setSelectedRoles] = useState<RoleSummary[]>(user?.roles ?? []);
  const [employeeChoice, setEmployeeChoice] = useState<number | null | "hidden">(
    user?.employee_link_hidden ? "hidden" : (user?.employee?.id ?? null),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [passwordInvalid, setPasswordInvalid] = useState(false);
  const [mfaInvalid, setMfaInvalid] = useState(false);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedRoles.length === 0) return;
    setError("");
    const missingPassword = currentPassword.length === 0;
    const missingMfaCode = mfaEnabled && mfaCode.length === 0;
    setPasswordInvalid(missingPassword);
    setMfaInvalid(missingMfaCode);
    if (missingPassword || missingMfaCode) return;
    setBusy(true);
    try {
      const authenticationFailure = await reauthenticateSensitiveAction(currentPassword, mfaCode);
      if (authenticationFailure) {
        setError(authenticationFailure.message);
        setPasswordInvalid(authenticationFailure.code === "invalid_current_password");
        setMfaInvalid(authenticationFailure.code === "invalid_mfa_code");
        return;
      }
      const body: Record<string, unknown> = user
        ? { name, status, role_ids: selectedRoles.map((role) => role.id) }
        : {
            name,
            email,
            temporary_password: password,
            role_ids: selectedRoles.map((role) => role.id),
          };
      if (canReadEmployees && employeeChoice !== "hidden") body.employee_id = employeeChoice;
      const response = await fetch(`/api/backend/users${user ? `/${user.id}` : ""}`, {
        method: user ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) return setError(await errorMessage(response));
      onSaved(user === null);
    } catch {
      setError("The user could not be saved. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword() {
    if (!user || password.length < 12)
      return setError("Enter a temporary password with at least 12 characters.");
    const missingPassword = currentPassword.length === 0;
    const missingMfaCode = mfaEnabled && mfaCode.length === 0;
    setPasswordInvalid(missingPassword);
    setMfaInvalid(missingMfaCode);
    if (missingPassword || missingMfaCode) return;
    setError("");
    setBusy(true);
    try {
      const authenticationFailure = await reauthenticateSensitiveAction(currentPassword, mfaCode);
      if (authenticationFailure) {
        setError(authenticationFailure.message);
        setPasswordInvalid(authenticationFailure.code === "invalid_current_password");
        setMfaInvalid(authenticationFailure.code === "invalid_mfa_code");
        return;
      }
      const response = await fetch(`/api/backend/users/${user.id}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ temporary_password: password }),
      });
      if (!response.ok) return setError(await errorMessage(response));
      onSaved(false);
    } catch {
      setError("The password could not be reset. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <form className="form-dialog access-form-dialog" onSubmit={submit}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">Human account</p>
            <h2>{user ? `Edit ${user.name}` : "Create a user"}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">
          <div className="field-grid">
            <label className="field">
              <span className="field-label">Full name</span>
              <input
                className="input"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">Email</span>
              <input
                className="input"
                type="email"
                required
                disabled={Boolean(user)}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">
                {user ? "New temporary password" : "Temporary password"}
              </span>
              <input
                className="input"
                type="password"
                required={!user}
                minLength={12}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {user && (
              <label className="field">
                <span className="field-label">Account status</span>
                <select
                  className="select"
                  value={status}
                  onChange={(event) => setStatus(event.target.value as UserDirectoryItem["status"])}
                >
                  <option value="active">Active</option>
                  <option value="suspended">Suspended</option>
                  <option value="disabled">Disabled</option>
                </select>
              </label>
            )}
            {canReadEmployees && (
              <div className="field full">
                <span className="field-label">Linked employee</span>
                {employeeChoice === "hidden" ? (
                  <div className="candidate-hidden-link">
                    <span>Outside your employee scope (unchanged)</span>
                    <Button
                      variant="secondary"
                      type="button"
                      onClick={() => setEmployeeChoice(null)}
                    >
                      Change link
                    </Button>
                  </div>
                ) : (
                  <EmployeeCombobox
                    userId={user?.id}
                    initialCandidate={user?.employee ?? undefined}
                    onChange={setEmployeeChoice}
                  />
                )}
              </div>
            )}
          </div>
          <RoleMultiSelect selected={selectedRoles} onChange={setSelectedRoles} />
          {selectedRoles.length === 0 && (
            <div className="role-required-message" role="alert">
              <CircleAlert size={13} />
              <span>Select at least one role.</span>
            </div>
          )}
        </div>
        <SensitiveConfirmation
          password={currentPassword}
          mfaCode={mfaCode}
          mfaEnabled={mfaEnabled}
          passwordInvalid={passwordInvalid}
          mfaInvalid={mfaInvalid}
          onPasswordChange={(value) => {
            setCurrentPassword(value);
            setPasswordInvalid(false);
            setError("");
          }}
          onMfaCodeChange={(value) => {
            setMfaCode(value);
            setMfaInvalid(false);
            setError("");
          }}
        />
        {error && (
          <div className="error-banner dialog-error" role="alert">
            <CircleAlert size={14} />
            <span>{error}</span>
          </div>
        )}
        <div className="form-footer">
          <span className="form-hint">
            New users must change their temporary password at first sign-in.
          </span>
          <div className="heading-actions">
            {user && (
              <Button
                variant="secondary"
                type="button"
                disabled={busy || password.length < 12}
                onClick={resetPassword}
              >
                <KeyRound size={14} /> Reset password
              </Button>
            )}
            <Button variant="secondary" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy || selectedRoles.length === 0}>
              {busy ? "Saving…" : "Save user"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}

function RoleCombobox({
  selected,
  onChange,
  placeholder,
}: {
  selected: RoleCandidate | null;
  onChange(role: RoleCandidate | null): void;
  placeholder: string;
}) {
  const listboxId = useId();
  const [query, setQuery] = useState(selected?.name ?? "");
  const [open, setOpen] = useState(false);
  const { results, loading, failed } = useRoleCandidates(
    open,
    query === selected?.name ? "" : query,
  );

  function choose(role: RoleCandidate | null) {
    onChange(role);
    setQuery(role?.name ?? "");
    setOpen(false);
  }

  return (
    <div
      className="manager-combobox access-candidate-combobox"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <div className="manager-combobox-control">
        <Search size={14} aria-hidden="true" />
        <input
          className="input"
          role="combobox"
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={open}
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            onChange(null);
            setOpen(true);
          }}
          placeholder={placeholder}
        />
        {(query || selected) && (
          <button
            className="manager-combobox-clear"
            type="button"
            onClick={() => choose(null)}
            aria-label="Clear role filter"
          >
            <X size={14} />
          </button>
        )}
      </div>
      {open && (
        <div className="manager-combobox-results" id={listboxId} role="listbox">
          {results.map((role) => (
            <button
              className="manager-combobox-option"
              type="button"
              role="option"
              aria-selected={selected?.id === role.id}
              key={role.id}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(role)}
            >
              {role.name}
            </button>
          ))}
          {loading && <div className="manager-combobox-status">Searching…</div>}
          {!loading && failed && (
            <div className="manager-combobox-status">Role search is unavailable.</div>
          )}
          {!loading && !failed && results.length === 0 && (
            <div className="manager-combobox-status">No matching roles.</div>
          )}
        </div>
      )}
    </div>
  );
}

function RoleMultiSelect({
  selected,
  onChange,
}: {
  selected: RoleSummary[];
  onChange(roles: RoleSummary[]): void;
}) {
  const listboxId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const { results, loading, failed } = useRoleCandidates(open, query);

  function add(role: RoleCandidate) {
    if (!selected.some((item) => item.id === role.id))
      onChange([...selected, { id: role.id, name: role.name }]);
    setQuery("");
    setOpen(false);
  }

  return (
    <fieldset className="role-options role-picker">
      <legend>Assigned roles</legend>
      <div className="permission-chip-list selected-candidates">
        {selected.map((role) => (
          <Badge className="selected-candidate" key={role.id}>
            {role.name}
            <button
              type="button"
              onClick={() => onChange(selected.filter((item) => item.id !== role.id))}
              aria-label={`Remove ${role.name}`}
            >
              <X size={11} />
            </button>
          </Badge>
        ))}
      </div>
      <div
        className="manager-combobox"
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
        }}
      >
        <div className="manager-combobox-control">
          <Search size={14} aria-hidden="true" />
          <input
            className="input"
            role="combobox"
            aria-autocomplete="list"
            aria-controls={listboxId}
            aria-expanded={open}
            value={query}
            onFocus={() => setOpen(true)}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
            placeholder="Search roles to assign"
          />
        </div>
        {open && (
          <div className="manager-combobox-results" id={listboxId} role="listbox">
            {results.map((role) => (
              <button
                className="manager-combobox-option candidate-detail"
                type="button"
                role="option"
                aria-selected={selected.some((item) => item.id === role.id)}
                disabled={selected.some((item) => item.id === role.id)}
                key={role.id}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => add(role)}
              >
                <strong>{role.name}</strong>
                <small>
                  {role.permission_count} permissions · {role.user_count} users
                </small>
              </button>
            ))}
            {loading && <div className="manager-combobox-status">Searching…</div>}
            {!loading && failed && (
              <div className="manager-combobox-status">Role search is unavailable.</div>
            )}
            {!loading && !failed && results.length === 0 && (
              <div className="manager-combobox-status">No matching roles.</div>
            )}
          </div>
        )}
      </div>
    </fieldset>
  );
}

function useRoleCandidates(open: boolean, query: string) {
  const [results, setResults] = useState<RoleCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setFailed(false);
      try {
        const params = new URLSearchParams({ limit: "20" });
        if (query.trim()) params.set("search", query.trim());
        const response = await fetch(`/api/backend/authorization/role-candidates?${params}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Role search failed");
        setResults(await response.json());
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setResults([]);
          setFailed(true);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [open, query]);
  return { results, loading, failed };
}

function EmployeeCombobox({
  userId,
  initialCandidate,
  onChange,
}: {
  userId?: number;
  initialCandidate?: EmployeeCandidate;
  onChange(id: number | null): void;
}) {
  const listboxId = useId();
  const [query, setQuery] = useState(initialCandidate ? employeeLabel(initialCandidate) : "");
  const [selected, setSelected] = useState<EmployeeCandidate | null>(initialCandidate ?? null);
  const [results, setResults] = useState<EmployeeCandidate[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setFailed(false);
      try {
        const params = new URLSearchParams({ limit: "20" });
        if (query.trim() && query !== (selected ? employeeLabel(selected) : ""))
          params.set("search", query.trim());
        if (userId) params.set("user_id", String(userId));
        const response = await fetch(`/api/backend/authorization/employee-candidates?${params}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Employee search failed");
        setResults(await response.json());
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setResults([]);
          setFailed(true);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [open, query, selected, userId]);

  function choose(candidate: EmployeeCandidate | null) {
    setSelected(candidate);
    setQuery(candidate ? employeeLabel(candidate) : "");
    onChange(candidate?.id ?? null);
    setOpen(false);
  }

  return (
    <div
      className="manager-combobox"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <div className="manager-combobox-control">
        <Search size={14} aria-hidden="true" />
        <input
          className="input"
          role="combobox"
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={open}
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setSelected(null);
            onChange(null);
            setOpen(true);
          }}
          placeholder="Search by name, department, or Employee ID"
        />
        {(query || selected) && (
          <button
            className="manager-combobox-clear"
            type="button"
            onClick={() => choose(null)}
            aria-label="Clear employee link"
          >
            <X size={14} />
          </button>
        )}
      </div>
      {open && (
        <div className="manager-combobox-results" id={listboxId} role="listbox">
          <button
            className="manager-combobox-option"
            type="button"
            role="option"
            aria-selected={selected === null && query === ""}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => choose(null)}
          >
            No employee link
          </button>
          {results.map((candidate) => (
            <button
              className="manager-combobox-option"
              type="button"
              role="option"
              aria-selected={selected?.id === candidate.id}
              key={candidate.id}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(candidate)}
            >
              {employeeLabel(candidate)}
            </button>
          ))}
          {loading && <div className="manager-combobox-status">Searching…</div>}
          {!loading && failed && (
            <div className="manager-combobox-status">Employee search is unavailable.</div>
          )}
          {!loading && !failed && results.length === 0 && query && (
            <div className="manager-combobox-status">No matching employees.</div>
          )}
        </div>
      )}
    </div>
  );
}

function employeeLabel(employee: EmployeeCandidate) {
  return `${employee.name} · ${employee.department} · ${formatEmployeeId(employee.id)}`;
}

function SensitiveConfirmation({
  password,
  mfaCode,
  mfaEnabled,
  passwordInvalid,
  mfaInvalid,
  onPasswordChange,
  onMfaCodeChange,
}: {
  password: string;
  mfaCode: string;
  mfaEnabled: boolean;
  passwordInvalid: boolean;
  mfaInvalid: boolean;
  onPasswordChange(value: string): void;
  onMfaCodeChange(value: string): void;
}) {
  return (
    <div className={`sensitive-confirmation${mfaEnabled ? " with-mfa" : ""}`}>
      <label className="field">
        <span className="field-label">
          Confirm your password <span className="required">Required</span>
        </span>
        <input
          className={`input${passwordInvalid ? " field-invalid" : ""}`}
          type="password"
          autoComplete="current-password"
          aria-required="true"
          aria-invalid={passwordInvalid}
          value={password}
          onChange={(event) => onPasswordChange(event.target.value)}
        />
      </label>
      {mfaEnabled && (
        <label className="field">
          <span className="field-label">
            MFA Code <span className="required">Required</span>
          </span>
          <input
            className={`input${mfaInvalid ? " field-invalid" : ""}`}
            inputMode="numeric"
            autoComplete="one-time-code"
            aria-required="true"
            aria-invalid={mfaInvalid}
            value={mfaCode}
            onChange={(event) => onMfaCodeChange(event.target.value)}
          />
        </label>
      )}
    </div>
  );
}

type RequestFailure = { code?: string; message: string };

async function reauthenticateSensitiveAction(
  password: string,
  mfaCode: string,
): Promise<RequestFailure | null> {
  const response = await fetch("/api/backend/auth/reauthenticate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password, ...(mfaCode ? { mfa_code: mfaCode } : {}) }),
  });
  return response.ok ? null : requestFailure(response);
}

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

async function errorMessage(response: Response): Promise<string> {
  return (await requestFailure(response)).message;
}
