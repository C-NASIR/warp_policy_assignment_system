from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.dates import current_datetime
from app.models import (
    AssignmentFieldDefinition,
    AuthSession,
    AutomatedUserRole,
    Employee,
    Role,
    RoleAssignmentFieldScope,
    RolePermission,
    User,
    UserRole,
)
from app.services.audit import record_audit_log, snapshot_entity
from app.services.human_auth import hash_password, normalize_email

WILDCARD_PERMISSION = "*"
AUTOMATION_FORBIDDEN_PERMISSIONS = frozenset(
    {WILDCARD_PERMISSION, "access:manage", "api_credentials:manage"}
)

PERMISSIONS: dict[str, tuple[str, str, str]] = {
    "employees:read": ("Employees", "View employees", "View employee profiles and employment facts."),
    "employees:create": ("Employees", "Create employees", "Add employees and preview their initial assignments."),
    "employees:update": ("Employees", "Update employees", "Change employee facts that can affect assignments."),
    "employees:delete": ("Employees", "Delete employees", "Remove employees from the workspace."),
    "policies:read": ("Policies", "View policies", "View policies, versions, rules, and impact."),
    "policies:create": ("Policies", "Create policies", "Create policies and their first version."),
    "policies:update": (
        "Policies",
        "Full policy management (legacy)",
        "Edit policy metadata, add versions, and change lifecycle state. Existing roles keep this combined grant.",
    ),
    "policies:version:create": (
        "Policies",
        "Create policy versions",
        "Add versions to draft policies; activating production behavior remains a separate permission.",
    ),
    "policies:activate": (
        "Policies",
        "Activate policies",
        "Activate draft or archived policies and authorize new versions of active policies.",
    ),
    "policies:archive": (
        "Policies",
        "Archive policies",
        "Stop a policy from participating in assignment resolution.",
    ),
    "groups:read": ("Groups", "View groups", "View groups and their policy connections."),
    "groups:create": ("Groups", "Create groups", "Create employee groups."),
    "groups:update": ("Groups", "Manage groups", "Rename groups and change membership or attached policies."),
    "assignments:read": ("Assignments", "View assignments", "View resolved assignments, history, and explanations."),
    "assignments:manage": ("Assignments", "Manage assignments", "Refresh assignments and manage manual overrides."),
    "settings:read": ("Configuration", "View assignment fields", "View assignment and condition-field configuration."),
    "settings:manage": ("Configuration", "Manage assignment fields", "Create assignment output fields."),
    "audit:read": ("Audit", "View audit log", "Inspect recorded changes and their actors."),
    "access:read": ("Access control", "View users and roles", "View users, roles, and the permission catalog."),
    "access:manage": ("Access control", "Manage users and roles", "Create and update users, roles, and role assignments."),
    "api_credentials:manage": ("Integrations", "Manage API credentials", "Create, list, and revoke machine credentials."),
    "changes:preview": ("Changes", "Preview changes", "Calculate the effects of supported changes before saving."),
    "changes:execute": ("Changes", "Execute approved changes", "Commit a previously approved change preview."),
    "changes:approve": (
        "Changes",
        "Approve sensitive changes",
        "Review and approve another user's pending change request.",
    ),
}


class PermissionDeniedError(Exception):
    def __init__(self, *, required: set[str], granted: set[str]) -> None:
        super().__init__("Your roles do not grant the required permission")
        self.code = "insufficient_permission"
        self.metadata = {
            "required_permissions": sorted(required),
            "granted_permissions": sorted(granted),
        }


def authorize_permissions(granted: frozenset[str], required: set[str]) -> None:
    if WILDCARD_PERMISSION in granted or required <= granted:
        return
    raise PermissionDeniedError(required=required, granted=set(granted))


def required_permissions(method: str, path: str) -> set[str]:
    method = method.upper()
    if path.startswith(("/users", "/roles", "/authorization")):
        return {"access:read"} if method == "GET" else {"access:manage"}
    if path.startswith("/auth/credentials") or path == "/auth/scopes":
        return {"api_credentials:manage"}
    if path.startswith("/audit-logs"):
        return {"audit:read"}
    if path.startswith("/change-previews"):
        return {"changes:preview"}
    if path.startswith("/change-executions"):
        return {"changes:execute"}
    if path.startswith("/approval-requests"):
        return {"changes:approve"}
    if path.startswith("/assignment-fields"):
        return {"settings:read"} if method == "GET" else {"settings:manage"}
    if path.startswith("/condition-fields"):
        return {"settings:read"}
    if path.startswith(("/assignment-summary", "/assignment-queries")):
        return {"assignments:read"}
    if path.startswith("/employees"):
        if "/assignments" in path or "/overrides" in path or path.endswith("/refresh"):
            return {"assignments:read"} if method == "GET" else {"assignments:manage"}
        if method == "GET":
            return {"employees:read"}
        if method == "POST":
            return {"employees:create"}
        if method == "PATCH":
            return {"employees:update"}
        if method == "DELETE":
            return {"employees:delete"}
    if path.startswith("/groups"):
        if method == "GET":
            return {"groups:read"}
        return {"groups:create"} if method == "POST" and path == "/groups" else {"groups:update"}
    if path.startswith("/policies"):
        if method == "GET":
            return {"policies:read"}
        if method == "POST" and path == "/policies":
            return {"policies:create"}
        # Policy routes enforce the specific version/lifecycle permission after
        # loading the record. This keeps the middleware contract precise while
        # retaining policies:update as a backwards-compatible combined grant.
        return set()
    return set()


def effective_permissions(session: Session, user: User) -> frozenset[str]:
    if user.is_root:
        return frozenset({WILDCARD_PERMISSION})
    explicit_values = set(session.scalars(
        select(RolePermission.permission)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user.id)
    ))
    automated_values = set(
        session.scalars(
            select(RolePermission.permission)
            .join(
                AutomatedUserRole,
                AutomatedUserRole.role_id == RolePermission.role_id,
            )
            .where(AutomatedUserRole.user_id == user.id)
        )
    )
    return frozenset(explicit_values | automated_values)


def role_by_id(session: Session, role_id: int) -> Role:
    role = session.scalar(
        select(Role)
        .options(
            selectinload(Role.permission_links),
            selectinload(Role.assignment_field_links),
            selectinload(Role.policy_grants),
            selectinload(Role.automated_user_links),
            selectinload(Role.users),
        )
        .where(Role.id == role_id)
    )
    if role is None:
        raise LookupError(f"Role {role_id} was not found")
    return role


def validate_permissions(permissions: Iterable[str]) -> list[str]:
    normalized = sorted(set(permissions))
    unknown = sorted(set(normalized) - set(PERMISSIONS))
    if unknown:
        raise ValueError(f"Unknown permissions: {', '.join(unknown)}")
    return normalized


def create_role(
    session: Session,
    *,
    name: str,
    description: str | None,
    permissions: Iterable[str],
    employee_scope: str,
    assignment_field_scope: str,
    assignment_field_ids: Iterable[int],
    automation_eligible: bool,
    actor: str,
) -> Role:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Role name cannot be blank")
    if session.scalar(select(Role.id).where(func.lower(Role.name) == normalized_name.casefold())):
        raise ValueError("A role with this name already exists")
    normalized_permissions = validate_permissions(permissions)
    _validate_automation_eligibility(
        normalized_name,
        normalized_permissions,
        automation_eligible,
    )
    role = Role(
        name=normalized_name,
        description=description.strip() if description else None,
        employee_scope=employee_scope,
        assignment_field_scope=assignment_field_scope,
        automation_eligible=automation_eligible,
        created_by=actor,
    )
    role.permission_links = [
        RolePermission(permission=permission)
        for permission in normalized_permissions
    ]
    role.assignment_field_links = _assignment_field_links(
        session,
        assignment_field_scope,
        assignment_field_ids,
    )
    session.add(role)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="Role",
        entity_id=role.id,
        action="created",
        before=None,
        after=role_snapshot(role),
    )
    return role


def update_role(
    session: Session,
    role: Role,
    *,
    name: str | None,
    description: str | None,
    permissions: Iterable[str] | None,
    employee_scope: str | None,
    assignment_field_scope: str | None,
    assignment_field_ids: Iterable[int] | None,
    automation_eligible: bool | None,
    description_supplied: bool,
    actor: str,
) -> Role:
    before = role_snapshot(role)
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Role name cannot be blank")
        duplicate = session.scalar(
            select(Role.id).where(
                func.lower(Role.name) == normalized_name.casefold(),
                Role.id != role.id,
            )
        )
        if duplicate:
            raise ValueError("A role with this name already exists")
        role.name = normalized_name
    if description_supplied:
        role.description = description.strip() if description else None
    if permissions is not None:
        role.permission_links = [
            RolePermission(permission=permission)
            for permission in validate_permissions(permissions)
        ]
    resulting_name = role.name
    resulting_permissions = [link.permission for link in role.permission_links]
    resulting_automation_eligible = (
        role.automation_eligible
        if automation_eligible is None
        else automation_eligible
    )
    if automation_eligible is False and role.policy_grants:
        raise ValueError(
            "A role referenced by an automated policy cannot disable automation"
        )
    _validate_automation_eligibility(
        resulting_name,
        resulting_permissions,
        resulting_automation_eligible,
    )
    if automation_eligible is not None:
        role.automation_eligible = automation_eligible
    if employee_scope is not None:
        role.employee_scope = employee_scope
    resulting_field_scope = assignment_field_scope or role.assignment_field_scope
    if assignment_field_scope is not None:
        role.assignment_field_scope = assignment_field_scope
    if assignment_field_scope is not None or assignment_field_ids is not None:
        if assignment_field_ids is not None:
            selected_ids = assignment_field_ids
        elif resulting_field_scope == "selected":
            selected_ids = [
                link.assignment_field_definition_id
                for link in role.assignment_field_links
            ]
        else:
            selected_ids = []
        role.assignment_field_links = _assignment_field_links(
            session,
            resulting_field_scope,
            selected_ids,
        )
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="Role",
        entity_id=role.id,
        action="updated",
        before=before,
        after=role_snapshot(role),
    )
    return role


def delete_role(session: Session, role: Role, *, actor: str) -> None:
    if role.users:
        raise ValueError("A role assigned to users cannot be deleted")
    if role.automated_user_links:
        raise ValueError("A role assigned by an automated policy cannot be deleted")
    if role.policy_grants:
        raise ValueError("A role referenced by an automated policy cannot be deleted")
    before = role_snapshot(role)
    role_id = role.id
    session.delete(role)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="Role",
        entity_id=role_id,
        action="deleted",
        before=before,
        after=None,
    )


def user_by_id(session: Session, user_id: int) -> User:
    user = session.scalar(
        select(User).options(selectinload(User.roles).selectinload(Role.permission_links)).where(User.id == user_id)
    )
    if user is None:
        raise LookupError(f"User {user_id} was not found")
    return user


def roles_by_ids(session: Session, role_ids: Iterable[int]) -> list[Role]:
    unique_ids = sorted(set(role_ids))
    roles = list(session.scalars(select(Role).where(Role.id.in_(unique_ids)).order_by(Role.id))) if unique_ids else []
    if len(roles) != len(unique_ids):
        found = {role.id for role in roles}
        missing = [str(role_id) for role_id in unique_ids if role_id not in found]
        raise ValueError(f"Unknown role IDs: {', '.join(missing)}")
    return roles


def create_user(
    session: Session,
    *,
    name: str,
    email: str,
    password: str,
    role_ids: Iterable[int],
    employee_id: int | None,
    actor: str,
) -> User:
    normalized_email = normalize_email(email)
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("User name cannot be blank")
    if session.scalar(select(User.id).where(User.email == normalized_email)):
        raise ValueError("A user with this email already exists")
    roles = roles_by_ids(session, role_ids)
    if not roles:
        raise ValueError("A non-Root user must have at least one role")
    _validate_employee_link(session, employee_id)
    user = User(
        name=normalized_name,
        email=normalized_email,
        password_hash=hash_password(password),
        status="active",
        is_root=False,
        password_change_required=True,
        employee_id=employee_id,
        roles=roles,
    )
    session.add(user)
    session.flush()
    if employee_id is not None:
        from app.services.reconciliation import reconcile_employees

        reconcile_employees(session, [employee_id], actor=actor)
    record_audit_log(
        session,
        actor=actor,
        entity_type="User",
        entity_id=user.id,
        action="created",
        before=None,
        after=user_snapshot(user),
    )
    return user


def update_user(
    session: Session,
    user: User,
    *,
    name: str | None,
    status: str | None,
    role_ids: Iterable[int] | None,
    employee_id: int | None,
    employee_id_supplied: bool,
    actor: str,
    actor_user_id: int,
) -> User:
    if user.is_root:
        raise ValueError("The Root user cannot be modified through user management")
    before = user_snapshot(user)
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("User name cannot be blank")
        user.name = normalized_name
    if status is not None:
        if user.id == actor_user_id and status != "active":
            raise ValueError("You cannot suspend or disable your own account")
        user.status = status
        if status != "active":
            revoke_user_sessions(session, user)
    if role_ids is not None:
        if user.id == actor_user_id:
            raise ValueError("You cannot change your own role assignments")
        roles = roles_by_ids(session, role_ids)
        if not roles:
            raise ValueError("A non-Root user must have at least one role")
        user.roles = roles
    if employee_id_supplied:
        from app.services.automated_access import clear_automated_roles_for_user
        from app.services.reconciliation import reconcile_employees

        _validate_employee_link(session, employee_id, user_id=user.id)
        if user.employee_id is not None and employee_id is None:
            clear_automated_roles_for_user(
                session,
                user,
                actor=actor,
                timestamp=current_datetime(),
            )
        user.employee_id = employee_id
        session.flush()
        if employee_id is not None:
            reconcile_employees(session, [employee_id], actor=actor)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="User",
        entity_id=user.id,
        action="updated",
        before=before,
        after=user_snapshot(user),
    )
    return user


def reset_user_password(
    session: Session,
    user: User,
    *,
    password: str,
    actor: str,
) -> None:
    if user.is_root:
        raise ValueError("Use account security to change the Root password")
    user.password_hash = hash_password(password)
    user.password_change_required = True
    revoke_user_sessions(session, user)
    record_audit_log(
        session,
        actor=actor,
        entity_type="User",
        entity_id=user.id,
        action="password_reset",
        before=None,
        after={"password_change_required": True},
    )


def disable_user(session: Session, user: User, *, actor: str, actor_user_id: int) -> None:
    if user.is_root:
        raise ValueError("The Root user cannot be deleted")
    if user.id == actor_user_id:
        raise ValueError("You cannot delete your own account")
    before = user_snapshot(user)
    user.status = "disabled"
    revoke_user_sessions(session, user)
    record_audit_log(
        session,
        actor=actor,
        entity_type="User",
        entity_id=user.id,
        action="disabled",
        before=before,
        after=user_snapshot(user),
    )


def revoke_user_sessions(session: Session, user: User) -> None:
    now = current_datetime()
    for auth_session in session.scalars(
        select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
    ):
        auth_session.revoked_at = now


def role_snapshot(role: Role) -> dict:
    return {
        "name": role.name,
        "description": role.description,
        "employee_scope": role.employee_scope,
        "assignment_field_scope": role.assignment_field_scope,
        "assignment_field_ids": sorted(
            link.assignment_field_definition_id
            for link in role.assignment_field_links
        ),
        "automation_eligible": role.automation_eligible,
        "permissions": sorted(link.permission for link in role.permission_links),
    }


def _assignment_field_links(
    session: Session,
    scope: str,
    assignment_field_ids: Iterable[int],
) -> list[RoleAssignmentFieldScope]:
    unique_ids = sorted(set(assignment_field_ids))
    if scope == "selected" and not unique_ids:
        raise ValueError("Selected assignment fields must include at least one field")
    if scope != "selected" and unique_ids:
        raise ValueError("Assignment field IDs are only valid for selected scope")
    found_ids = set(
        session.scalars(
            select(AssignmentFieldDefinition.id).where(
                AssignmentFieldDefinition.id.in_(unique_ids)
            )
        )
    )
    missing = [str(field_id) for field_id in unique_ids if field_id not in found_ids]
    if missing:
        raise ValueError(f"Unknown assignment field IDs: {', '.join(missing)}")
    return [
        RoleAssignmentFieldScope(assignment_field_definition_id=field_id)
        for field_id in unique_ids
    ]


def _validate_automation_eligibility(
    name: str,
    permissions: Iterable[str],
    automation_eligible: bool,
) -> None:
    if not automation_eligible:
        return
    if name.casefold() == "root":
        raise ValueError("The Root role cannot be granted by policy")
    forbidden = sorted(set(permissions) & AUTOMATION_FORBIDDEN_PERMISSIONS)
    if forbidden:
        raise ValueError(
            "Roles granted by policy cannot contain protected permissions: "
            + ", ".join(forbidden)
        )


def user_snapshot(user: User) -> dict:
    return {
        **snapshot_entity(user, exclude={"password_hash"}),
        "role_ids": sorted(role.id for role in user.roles),
    }


def _validate_employee_link(session: Session, employee_id: int | None, *, user_id: int | None = None) -> None:
    if employee_id is None:
        return
    if session.get(Employee, employee_id) is None:
        raise ValueError(f"Employee {employee_id} was not found")
    statement = select(User.id).where(User.employee_id == employee_id)
    if user_id is not None:
        statement = statement.where(User.id != user_id)
    if session.scalar(statement):
        raise ValueError("This employee is already linked to another user")
