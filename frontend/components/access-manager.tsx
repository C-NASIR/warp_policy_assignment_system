"use client";

import { Check, CircleAlert, KeyRound, Pencil, Plus, ShieldCheck, Trash2, Users } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import type { Permission, Role, User } from "@/lib/types";

type Props = {
  initialUsers: User[];
  initialRoles: Role[];
  permissions: Permission[];
  canManage: boolean;
  apiConfigured: boolean;
};

export function AccessManager({ initialUsers, initialRoles, permissions, canManage, apiConfigured }: Props) {
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

  return <>
    <div className="page-heading"><div><p className="eyebrow">Authorization</p><h1>Access control</h1><p className="page-subtitle">Create reusable roles, choose their exact permissions, and assign those roles to human users.</p></div>{canManage && <button className="button" onClick={() => tab === "users" ? setEditingUser(null) : setEditingRole(null)}><Plus size={15} /> {tab === "users" ? "Create user" : "Create role"}</button>}</div>
    {message && <div className={message.type === "error" ? "error-banner" : "success-banner"} role={message.type === "error" ? "alert" : "status"}>{message.type === "error" ? <CircleAlert size={14} /> : <Check size={14} />}{message.text}</div>}
    <div className="segmented access-tabs" role="tablist"><button className={tab === "users" ? "active" : ""} role="tab" aria-selected={tab === "users"} onClick={() => setTab("users")}><Users size={14} /> Users</button><button className={tab === "roles" ? "active" : ""} role="tab" aria-selected={tab === "roles"} onClick={() => setTab("roles")}><ShieldCheck size={14} /> Roles</button></div>
    {tab === "users" ? <UsersPanel users={users} roles={roles} canManage={canManage} onEdit={setEditingUser} onDeleted={(id) => setUsers((current) => current.map((user) => user.id === id ? { ...user, status: "disabled" } : user))} onError={(text) => setMessage({ type: "error", text })} onComplete={completed} /> : <RolesPanel roles={roles} permissions={permissions} canManage={canManage} onEdit={setEditingRole} onDeleted={(id) => setRoles((current) => current.filter((role) => role.id !== id))} onError={(text) => setMessage({ type: "error", text })} />}
    {editingRole !== undefined && <RoleForm role={editingRole} permissions={permissions} apiConfigured={apiConfigured} onClose={() => setEditingRole(undefined)} onSaved={(role) => { setRoles((current) => editingRole ? current.map((item) => item.id === role.id ? role : item) : [...current, role].sort((a, b) => a.name.localeCompare(b.name))); setEditingRole(undefined); completed(editingRole ? "Role updated." : "Role created."); }} onError={(text) => setMessage({ type: "error", text })} />}
    {editingUser !== undefined && <UserForm user={editingUser} roles={roles} apiConfigured={apiConfigured} onClose={() => setEditingUser(undefined)} onSaved={(user) => { setUsers((current) => editingUser ? current.map((item) => item.id === user.id ? user : item) : [...current, user].sort((a, b) => a.name.localeCompare(b.name))); setEditingUser(undefined); completed(editingUser ? "User updated." : "User created with a temporary password."); }} onError={(text) => setMessage({ type: "error", text })} />}
  </>;
}

function UsersPanel({ users, roles, canManage, onEdit, onDeleted, onError, onComplete }: { users: User[]; roles: Role[]; canManage: boolean; onEdit(user: User): void; onDeleted(id: number): void; onError(text: string): void; onComplete(text: string): void }) {
  async function disable(user: User) {
    if (!window.confirm(`Disable ${user.name}? Their active sessions will end immediately.`)) return;
    const response = await fetch(`/api/backend/users/${user.id}`, { method: "DELETE" });
    if (!response.ok) return onError(await errorMessage(response));
    onDeleted(user.id); onComplete(`${user.name} was disabled.`);
  }
  return <div className="data-panel access-table"><table className="data-table"><thead><tr><th>User</th><th>Roles</th><th>Effective permissions</th><th>Status</th>{canManage && <th><span className="sr-only">Actions</span></th>}</tr></thead><tbody>{users.map((user) => <tr key={user.id}><td><span className="primary-cell">{user.name}</span><span className="secondary-cell">{user.email}</span></td><td>{user.is_root ? <span className="badge accent">Root</span> : user.roles.map((role) => <span className="badge" key={role.id}>{role.name}</span>)}</td><td><span className="primary-cell">{user.permissions.includes("*") ? "All permissions" : `${user.permissions.length} permissions`}</span>{user.password_change_required && <span className="secondary-cell">Password change required</span>}</td><td><span className={`badge ${user.status === "active" ? "success" : ""}`}>{user.status}</span></td>{canManage && <td><div className="row-actions">{!user.is_root && <><button className="icon-button" aria-label={`Edit ${user.name}`} onClick={() => onEdit(user)}><Pencil size={14} /></button><button className="icon-button danger-button" aria-label={`Disable ${user.name}`} disabled={user.status === "disabled"} onClick={() => disable(user)}><Trash2 size={14} /></button></>}</div></td>}</tr>)}</tbody></table><div className="pagination-footer"><span>{users.length} users</span><span>{roles.length} available roles</span></div></div>;
}

function RolesPanel({ roles, permissions, canManage, onEdit, onDeleted, onError }: { roles: Role[]; permissions: Permission[]; canManage: boolean; onEdit(role: Role): void; onDeleted(id: number): void; onError(text: string): void }) {
  async function remove(role: Role) {
    if (!window.confirm(`Delete the ${role.name} role?`)) return;
    const response = await fetch(`/api/backend/roles/${role.id}`, { method: "DELETE" });
    if (!response.ok) return onError(await errorMessage(response));
    onDeleted(role.id);
  }
  return <div className="role-grid">{roles.map((role) => <article className="panel role-card" key={role.id}><div className="role-card-head"><div className="role-icon"><ShieldCheck size={16} /></div>{canManage && <div className="row-actions"><button className="icon-button" aria-label={`Edit ${role.name}`} onClick={() => onEdit(role)}><Pencil size={14} /></button><button className="icon-button danger-button" aria-label={`Delete ${role.name}`} disabled={role.user_count > 0} onClick={() => remove(role)}><Trash2 size={14} /></button></div>}</div><h2>{role.name}</h2><p>{role.description || "No description provided."}</p><div className="role-card-meta"><span>{role.permissions.length} of {permissions.length} permissions</span><span>{role.user_count} users</span></div><div className="permission-chip-list">{role.permissions.slice(0, 5).map((permission) => <span className="badge" key={permission}>{permissions.find((item) => item.name === permission)?.label ?? permission}</span>)}{role.permissions.length > 5 && <span className="badge accent">+{role.permissions.length - 5}</span>}</div></article>)}{roles.length === 0 && <div className="empty-state panel"><div className="empty-icon"><ShieldCheck size={18} /></div><strong>No roles yet</strong><span>Create the first least-privilege role for your team.</span></div>}</div>;
}

function RoleForm({ role, permissions, apiConfigured, onClose, onSaved, onError }: { role: Role | null; permissions: Permission[]; apiConfigured: boolean; onClose(): void; onSaved(role: Role): void; onError(text: string): void }) {
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [selected, setSelected] = useState<string[]>(role?.permissions ?? []);
  const [busy, setBusy] = useState(false);
  const groups = useMemo(() => [...new Set(permissions.map((item) => item.group))], [permissions]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    const response = await fetch(`/api/backend/roles${role ? `/${role.id}` : ""}`, { method: role ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, description, permissions: selected }) });
    setBusy(false);
    if (!response.ok) return onError(await errorMessage(response));
    onSaved(await response.json());
  }
  function toggle(permission: string) { setSelected((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission]); }
  return <div className="modal-backdrop"><form className="form-dialog access-form-dialog" onSubmit={submit}><div className="modal-head"><div><p className="eyebrow">Permission bundle</p><h2>{role ? `Edit ${role.name}` : "Create a role"}</h2></div><button type="button" className="icon-button" onClick={onClose} aria-label="Close">×</button></div><div className="modal-body"><div className="field-grid"><label className="field"><span className="field-label">Role name</span><input className="input" required value={name} onChange={(event) => setName(event.target.value)} /></label><label className="field full"><span className="field-label">Description</span><textarea className="textarea" value={description} onChange={(event) => setDescription(event.target.value)} /></label></div><div className="permission-groups">{groups.map((group) => <fieldset key={group}><legend>{group}</legend>{permissions.filter((item) => item.group === group).map((permission) => <label className="permission-option" key={permission.name}><input type="checkbox" checked={selected.includes(permission.name)} onChange={() => toggle(permission.name)} /><span><strong>{permission.label}</strong><small>{permission.description}</small></span></label>)}</fieldset>)}</div></div><div className="form-footer"><span className="form-hint">{selected.length} permissions selected</span><div className="heading-actions"><button className="button secondary" type="button" onClick={onClose}>Cancel</button><button className="button" disabled={busy || !apiConfigured}>{busy ? "Saving…" : "Save role"}</button></div></div></form></div>;
}

function UserForm({ user, roles, apiConfigured, onClose, onSaved, onError }: { user: User | null; roles: Role[]; apiConfigured: boolean; onClose(): void; onSaved(user: User): void; onError(text: string): void }) {
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState(user?.status ?? "active");
  const [roleIds, setRoleIds] = useState<number[]>(user?.roles.map((role) => role.id) ?? []);
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    const body = user ? { name, status, role_ids: roleIds } : { name, email, temporary_password: password, role_ids: roleIds };
    const response = await fetch(`/api/backend/users${user ? `/${user.id}` : ""}`, { method: user ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    setBusy(false);
    if (!response.ok) return onError(await errorMessage(response));
    onSaved(await response.json());
  }
  async function resetPassword() {
    if (!user || password.length < 12) return onError("Enter a temporary password with at least 12 characters.");
    setBusy(true);
    const response = await fetch(`/api/backend/users/${user.id}/reset-password`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ temporary_password: password }) });
    setBusy(false);
    if (!response.ok) return onError(await errorMessage(response));
    onSaved(await response.json());
  }
  function toggle(roleId: number) { setRoleIds((current) => current.includes(roleId) ? current.filter((id) => id !== roleId) : [...current, roleId]); }
  return <div className="modal-backdrop"><form className="form-dialog access-form-dialog" onSubmit={submit}><div className="modal-head"><div><p className="eyebrow">Human account</p><h2>{user ? `Edit ${user.name}` : "Create a user"}</h2></div><button type="button" className="icon-button" onClick={onClose} aria-label="Close">×</button></div><div className="modal-body"><div className="field-grid"><label className="field"><span className="field-label">Full name</span><input className="input" required value={name} onChange={(event) => setName(event.target.value)} /></label><label className="field"><span className="field-label">Email</span><input className="input" type="email" required disabled={Boolean(user)} value={email} onChange={(event) => setEmail(event.target.value)} /></label><label className="field"><span className="field-label">{user ? "New temporary password" : "Temporary password"}</span><input className="input" type="password" required={!user} minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} /></label>{user && <label className="field"><span className="field-label">Account status</span><select className="select" value={status} onChange={(event) => setStatus(event.target.value as User["status"])}><option value="active">Active</option><option value="suspended">Suspended</option><option value="disabled">Disabled</option></select></label>}</div><fieldset className="role-options"><legend>Assigned roles</legend>{roles.map((role) => <label className="permission-option" key={role.id}><input type="checkbox" checked={roleIds.includes(role.id)} onChange={() => toggle(role.id)} /><span><strong>{role.name}</strong><small>{role.permissions.length} permissions · {role.user_count} users</small></span></label>)}</fieldset></div><div className="form-footer"><span className="form-hint">New users must change their temporary password at first sign-in.</span><div className="heading-actions">{user && <button className="button secondary" type="button" disabled={busy || password.length < 12} onClick={resetPassword}><KeyRound size={14} /> Reset password</button>}<button className="button secondary" type="button" onClick={onClose}>Cancel</button><button className="button" disabled={busy || !apiConfigured || roleIds.length === 0}>{busy ? "Saving…" : "Save user"}</button></div></div></form></div>;
}

async function errorMessage(response: Response): Promise<string> {
  const result = await response.json().catch(() => ({}));
  return result.error?.issues?.[0]?.message ?? result.error?.message ?? result.detail ?? `Request failed with ${response.status}`;
}
