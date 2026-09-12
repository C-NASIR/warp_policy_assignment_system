"use client";

import {
  Check,
  CircleAlert,
  KeyRound,
  Pencil,
  Plus,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";
import { type SubmitEvent, useMemo, useState } from "react";
import { Badge, Button, DataTable, Panel } from "@/components/ui";
import type { AssignmentField, Employee, Permission, Role, User } from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";

type Props = {
  initialUsers: User[];
  initialRoles: Role[];
  employees: Employee[];
  permissions: Permission[];
  assignmentFields: AssignmentField[];
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
  initialUsers,
  initialRoles,
  employees,
  permissions,
  assignmentFields,
  canManage,
  canReadEmployees,
  mfaEnabled,
}: Props) {
  const [tab, setTab] = useState<"users" | "roles">("users");
  const [users, setUsers] = useState(initialUsers);
  const [roles, setRoles] = useState(initialRoles);
  const [editingRole, setEditingRole] = useState<Role | null | undefined>(undefined);
  const [editingUser, setEditingUser] = useState<User | null | undefined>(undefined);
  const [message, setMessage] = useState<{ type: "error" | "success"; text: string } | null>(null);

  function completed(text: string) {
    setMessage({ type: "success", text });
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
          <Button onClick={() => (tab === "users" ? setEditingUser(null) : setEditingRole(null))}>
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
      <div className="segmented access-tabs" role="tablist">
        <button
          className={tab === "users" ? "active" : ""}
          role="tab"
          aria-selected={tab === "users"}
          onClick={() => setTab("users")}
        >
          <Users size={14} /> Users
        </button>
        <button
          className={tab === "roles" ? "active" : ""}
          role="tab"
          aria-selected={tab === "roles"}
          onClick={() => setTab("roles")}
        >
          <ShieldCheck size={14} /> Roles
        </button>
      </div>
      {tab === "users" ? (
        <UsersPanel
          users={users}
          roles={roles}
          employees={employees}
          canManage={canManage}
          onEdit={setEditingUser}
          onDeleted={(id) =>
            setUsers((current) =>
              current.map((user) => (user.id === id ? { ...user, status: "disabled" } : user)),
            )
          }
          onError={(text) => setMessage({ type: "error", text })}
          onComplete={completed}
        />
      ) : (
        <RolesPanel
          roles={roles}
          permissions={permissions}
          assignmentFields={assignmentFields}
          canManage={canManage}
          onEdit={setEditingRole}
          onDeleted={(id) => setRoles((current) => current.filter((role) => role.id !== id))}
          onError={(text) => setMessage({ type: "error", text })}
        />
      )}
      {editingRole !== undefined && (
        <RoleForm
          role={editingRole}
          permissions={permissions}
          assignmentFields={assignmentFields}
          mfaEnabled={mfaEnabled}
          onClose={() => setEditingRole(undefined)}
          onSaved={(role) => {
            setRoles((current) =>
              editingRole
                ? current.map((item) => (item.id === role.id ? role : item))
                : [...current, role].sort((a, b) => a.name.localeCompare(b.name)),
            );
            setEditingRole(undefined);
            completed(editingRole ? "Role updated." : "Role created.");
          }}
        />
      )}
      {editingUser !== undefined && (
        <UserForm
          user={editingUser}
          roles={roles}
          employees={employees}
          canReadEmployees={canReadEmployees}
          mfaEnabled={mfaEnabled}
          onClose={() => setEditingUser(undefined)}
          onSaved={(user) => {
            setUsers((current) =>
              editingUser
                ? current.map((item) => (item.id === user.id ? user : item))
                : [...current, user].sort((a, b) => a.name.localeCompare(b.name)),
            );
            setEditingUser(undefined);
            completed(editingUser ? "User updated." : "User created with a temporary password.");
          }}
        />
      )}
    </>
  );
}

function UsersPanel({
  users,
  roles,
  employees,
  canManage,
  onEdit,
  onDeleted,
  onError,
  onComplete,
}: {
  users: User[];
  roles: Role[];
  employees: Employee[];
  canManage: boolean;
  onEdit(user: User): void;
  onDeleted(id: number): void;
  onError(text: string): void;
  onComplete(text: string): void;
}) {
  async function disable(user: User) {
    if (!window.confirm(`Disable ${user.name}? Their active sessions will end immediately.`))
      return;
    const response = await fetch(`/api/backend/users/${user.id}`, { method: "DELETE" });
    if (!response.ok) return onError(await errorMessage(response));
    onDeleted(user.id);
    onComplete(`${user.name} was disabled.`);
  }
  return (
    <Panel as="div" className="access-table" clipped>
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
          {users.map((user) => {
            const employee = employees.find((item) => item.id === user.employee_id);
            return (
              <tr key={user.id}>
                <td>
                  <span className="primary-cell">{user.name}</span>
                  <span className="secondary-cell">{user.email}</span>
                </td>
                <td>
                  {user.employee_link_hidden ? (
                    <span className="secondary-cell">Outside your employee scope</span>
                  ) : employee ? (
                    <>
                      <span className="primary-cell">{employee.name}</span>
                      <span className="secondary-cell">{employee.department}</span>
                    </>
                  ) : (
                    <span className="secondary-cell">Not linked</span>
                  )}
                </td>
                <td>
                  {user.is_root ? (
                    <Badge tone="accent">Root</Badge>
                  ) : (
                    user.roles.map((role) => <Badge key={role.id}>{role.name}</Badge>)
                  )}
                </td>
                <td>
                  <span className="primary-cell">
                    {user.permissions.includes("*")
                      ? "All permissions"
                      : `${user.permissions.length} permissions`}
                  </span>
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
                            onClick={() => disable(user)}
                          >
                            <Trash2 size={14} />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </DataTable>
      <div className="pagination-footer">
        <span>{users.length} users</span>
        <span>{roles.length} available roles</span>
      </div>
    </Panel>
  );
}

function RolesPanel({
  roles,
  permissions,
  assignmentFields,
  canManage,
  onEdit,
  onDeleted,
  onError,
}: {
  roles: Role[];
  permissions: Permission[];
  assignmentFields: AssignmentField[];
  canManage: boolean;
  onEdit(role: Role): void;
  onDeleted(id: number): void;
  onError(text: string): void;
}) {
  async function remove(role: Role) {
    if (!window.confirm(`Delete the ${role.name} role?`)) return;
    const response = await fetch(`/api/backend/roles/${role.id}`, { method: "DELETE" });
    if (!response.ok) return onError(await errorMessage(response));
    onDeleted(role.id);
  }
  return (
    <div className="role-grid">
      {roles.map((role) => (
        <Panel as="article" className="role-card" key={role.id}>
          <div className="role-card-head">
            <div className="role-icon">
              <ShieldCheck size={16} />
            </div>
            {canManage && (
              <div className="row-actions">
                <button
                  className="icon-button"
                  aria-label={`Edit ${role.name}`}
                  onClick={() => onEdit(role)}
                >
                  <Pencil size={14} />
                </button>
                <button
                  className="icon-button danger-button"
                  aria-label={`Delete ${role.name}`}
                  disabled={role.user_count > 0}
                  onClick={() => remove(role)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            )}
          </div>
          <h2>{role.name}</h2>
          <p>{role.description || "No description provided."}</p>
          <div className="role-card-meta">
            <span>
              {role.permissions.length} of {permissions.length} permissions
            </span>
            <span>{role.user_count} users</span>
          </div>
          <div className="permission-chip-list">
            <Badge tone="accent">{employeeScopeLabels[role.employee_scope]}</Badge>
            <Badge tone="accent">
              {role.assignment_field_scope === "selected"
                ? `${role.assignment_field_ids.length} of ${assignmentFields.length} assignment fields`
                : assignmentFieldScopeLabels[role.assignment_field_scope]}
            </Badge>
            {role.permissions.slice(0, 5).map((permission) => (
              <Badge key={permission}>
                {permissions.find((item) => item.name === permission)?.label ?? permission}
              </Badge>
            ))}
            {role.permissions.length > 5 && (
              <Badge tone="accent">+{role.permissions.length - 5}</Badge>
            )}
          </div>
        </Panel>
      ))}
      {roles.length === 0 && (
        <Panel as="div" className="empty-state">
          <div className="empty-icon">
            <ShieldCheck size={18} />
          </div>
          <strong>No roles yet</strong>
          <span>Create the first least-privilege role for your team.</span>
        </Panel>
      )}
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
  assignmentFields: AssignmentField[];
  mfaEnabled: boolean;
  onClose(): void;
  onSaved(role: Role): void;
}) {
  useModalAccessibility(true, onClose);
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
      onSaved(await response.json());
    } catch {
      setError("The role could not be saved. Please try again.");
    } finally {
      setBusy(false);
    }
  }
  function toggle(permission: string) {
    setSelected((current) =>
      current.includes(permission)
        ? current.filter((item) => item !== permission)
        : [...current, permission],
    );
  }
  function toggleAssignmentField(fieldId: number) {
    setAssignmentFieldIds((current) =>
      current.includes(fieldId) ? current.filter((id) => id !== fieldId) : [...current, fieldId],
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
            Employee visibility controls whose records are accessible. Assignment field access
            independently controls which policy and assignment domains—such as Application Access or
            Pay Schedule—are accessible.
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
            <Button
              type="submit"
              disabled={
                busy || (assignmentFieldScope === "selected" && assignmentFieldIds.length === 0)
              }
            >
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
  roles,
  employees,
  canReadEmployees,
  mfaEnabled,
  onClose,
  onSaved,
}: {
  user: User | null;
  roles: Role[];
  employees: Employee[];
  canReadEmployees: boolean;
  mfaEnabled: boolean;
  onClose(): void;
  onSaved(user: User): void;
}) {
  useModalAccessibility(true, onClose);
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState(user?.status ?? "active");
  const [roleIds, setRoleIds] = useState<number[]>(user?.roles.map((role) => role.id) ?? []);
  const [employeeId, setEmployeeId] = useState(
    user?.employee_link_hidden ? "hidden" : String(user?.employee_id ?? ""),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [passwordInvalid, setPasswordInvalid] = useState(false);
  const [mfaInvalid, setMfaInvalid] = useState(false);
  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (roles.length === 0) return;
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
        ? { name, status, role_ids: roleIds }
        : { name, email, temporary_password: password, role_ids: roleIds };
      if (canReadEmployees && employeeId !== "hidden")
        body.employee_id = employeeId ? Number(employeeId) : null;
      const response = await fetch(`/api/backend/users${user ? `/${user.id}` : ""}`, {
        method: user ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) return setError(await errorMessage(response));
      onSaved(await response.json());
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
      onSaved(await response.json());
    } catch {
      setError("The password could not be reset. Please try again.");
    } finally {
      setBusy(false);
    }
  }
  function toggle(roleId: number) {
    setRoleIds((current) =>
      current.includes(roleId) ? current.filter((id) => id !== roleId) : [...current, roleId],
    );
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
                  onChange={(event) => setStatus(event.target.value as User["status"])}
                >
                  <option value="active">Active</option>
                  <option value="suspended">Suspended</option>
                  <option value="disabled">Disabled</option>
                </select>
              </label>
            )}
            {canReadEmployees && (
              <label className="field full">
                <span className="field-label">Linked employee</span>
                <select
                  className="select"
                  value={employeeId}
                  onChange={(event) => setEmployeeId(event.target.value)}
                >
                  {user?.employee_link_hidden && (
                    <option value="hidden">Outside your employee scope (unchanged)</option>
                  )}
                  <option value="">No employee link</option>
                  {employees.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.name} · {employee.department}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          {roles.length === 0 && (
            <div className="role-required-message" role="alert">
              <CircleAlert size={13} />
              <span>Create role first.</span>
            </div>
          )}
          <fieldset className="role-options">
            <legend>Assigned roles</legend>
            {roles.map((role) => (
              <label className="permission-option" key={role.id}>
                <input
                  type="checkbox"
                  checked={roleIds.includes(role.id)}
                  onChange={() => toggle(role.id)}
                />
                <span>
                  <strong>{role.name}</strong>
                  <small>
                    {employeeScopeLabels[role.employee_scope]} ·{" "}
                    {role.assignment_field_scope === "selected"
                      ? `${role.assignment_field_ids.length} assignment fields`
                      : assignmentFieldScopeLabels[role.assignment_field_scope]}{" "}
                    · {role.permissions.length} permissions · {role.user_count} users
                  </small>
                </span>
              </label>
            ))}
          </fieldset>
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
            <Button type="submit" disabled={busy || roles.length === 0 || roleIds.length === 0}>
              {busy ? "Saving…" : "Save user"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
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
      result.detail ??
      `Request failed with ${response.status}`,
  };
}

async function errorMessage(response: Response): Promise<string> {
  return (await requestFailure(response)).message;
}
