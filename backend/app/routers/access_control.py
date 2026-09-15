from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import load_only, selectinload

from app.dependencies import Authenticated, DatabaseSession, EmployeeScope
from app.models import (
    AssignmentFieldDefinition,
    Employee,
    Role,
    RoleAssignmentFieldScope,
    RolePermission,
    User,
    UserRole,
)
from app.pagination import Pagination, paginate_scalars, paginate_sequence
from app.schemas import (
    AccessReviewRead,
    AssignmentFieldScopeOptionRead,
    EmployeeCandidateRead,
    EmployeeLinkSummaryRead,
    PermissionRead,
    RoleCandidateRead,
    RoleCreate,
    RoleDirectoryRead,
    RoleRead,
    RoleSummaryRead,
    RoleUpdate,
    UserCreate,
    UserDirectoryRead,
    UserPasswordResetCreate,
    UserRead,
    UserUpdate,
)
from app.services.access_control import (
    PERMISSIONS,
    access_review,
    create_role,
    create_user,
    delete_role,
    disable_user,
    effective_permissions,
    reset_user_password,
    role_by_id,
    update_role,
    update_user,
    user_by_id,
)
from app.services.employee_visibility import EmployeeVisibility, visible_employee_or_404

authorization_router = APIRouter(prefix="/authorization", tags=["authorization"])
roles_router = APIRouter(prefix="/roles", tags=["roles"])
users_router = APIRouter(prefix="/users", tags=["users"])


@authorization_router.get("/permissions", response_model=list[PermissionRead])
def list_permissions(
    response: Response,
    pagination: Pagination,
) -> list[PermissionRead]:
    values = [
        PermissionRead(name=name, group=group, label=label, description=description)
        for name, (group, label, description) in PERMISSIONS.items()
    ]
    return paginate_sequence(values, pagination, response)


@authorization_router.get("/access-review", response_model=AccessReviewRead)
def review_access(session: DatabaseSession) -> AccessReviewRead:
    return AccessReviewRead.model_validate(access_review(session))


@authorization_router.get(
    "/assignment-fields",
    response_model=list[AssignmentFieldScopeOptionRead],
)
def list_authorization_assignment_fields(
    session: DatabaseSession,
) -> list[AssignmentFieldScopeOptionRead]:
    """Expose the field catalog needed to configure role data scopes."""
    return [
        AssignmentFieldScopeOptionRead(id=field_id, name=name, cardinality=cardinality)
        for field_id, name, cardinality in session.execute(
            select(
                AssignmentFieldDefinition.id,
                AssignmentFieldDefinition.name,
                AssignmentFieldDefinition.cardinality,
            ).order_by(AssignmentFieldDefinition.name, AssignmentFieldDefinition.id)
        ).all()
    ]


@authorization_router.get(
    "/role-candidates",
    response_model=list[RoleCandidateRead],
)
def role_candidates(
    session: DatabaseSession,
    search: Annotated[str | None, Query(max_length=100)] = None,
    role_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[RoleCandidateRead]:
    statement = select(Role).options(
        load_only(Role.id, Role.name, Role.employee_scope, Role.assignment_field_scope),
        selectinload(Role.role_permissions).load_only(RolePermission.permission),
    )
    if role_id is not None:
        statement = statement.where(Role.id == role_id)
    elif search and search.strip():
        statement = statement.where(Role.name.ilike(f"%{search.strip()}%"))
    roles = list(session.scalars(statement.order_by(Role.name, Role.id).limit(limit)))
    role_ids = [role.id for role in roles]
    user_counts = _role_user_counts(session, role_ids)
    field_counts = _role_assignment_field_counts(session, role_ids)
    return [
        RoleCandidateRead(
            id=role.id,
            name=role.name,
            employee_scope=role.employee_scope,
            assignment_field_scope=role.assignment_field_scope,
            assignment_field_count=field_counts.get(role.id, 0),
            permission_count=len(role.role_permissions),
            user_count=user_counts.get(role.id, 0),
        )
        for role in roles
    ]


@authorization_router.get(
    "/employee-candidates",
    response_model=list[EmployeeCandidateRead],
)
def employee_candidates(
    session: DatabaseSession,
    visibility: EmployeeScope,
    search: Annotated[str | None, Query(max_length=200)] = None,
    user_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[EmployeeCandidateRead]:
    if (
        user_id is not None
        and session.scalar(select(User.id).where(User.id == user_id)) is None
    ):
        raise HTTPException(status_code=404, detail=f"User {user_id} was not found")

    statement = visibility.apply(
        select(Employee.id, Employee.name, Employee.department), Employee.id
    )
    linked_employee_ids = select(User.employee_id).where(User.employee_id.is_not(None))
    if user_id is not None:
        linked_employee_ids = linked_employee_ids.where(User.id != user_id)
    statement = statement.where(Employee.id.not_in(linked_employee_ids))
    if search and search.strip():
        value = search.strip()
        predicates = [
            Employee.name.ilike(f"%{value}%"),
            Employee.department.ilike(f"%{value}%"),
        ]
        searched_id = value.removeprefix("#")
        if searched_id.isdigit():
            predicates.append(Employee.id == int(searched_id))
        statement = statement.where(or_(*predicates))
    return [
        EmployeeCandidateRead(id=employee_id, name=name, department=department)
        for employee_id, name, department in session.execute(
            statement.order_by(Employee.name, Employee.id).limit(limit)
        ).all()
    ]


@roles_router.get("", response_model=list[RoleDirectoryRead])
def list_roles(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> list[RoleDirectoryRead]:
    statement = select(Role).options(
        load_only(
            Role.id,
            Role.name,
            Role.description,
            Role.employee_scope,
            Role.assignment_field_scope,
        ),
        selectinload(Role.role_permissions).load_only(RolePermission.permission),
    )
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(Role.name.ilike(pattern), Role.description.ilike(pattern))
        )
    roles = paginate_scalars(
        session, statement.order_by(Role.name, Role.id), pagination, response
    )
    role_ids = [role.id for role in roles]
    user_counts = _role_user_counts(session, role_ids)
    field_counts = _role_assignment_field_counts(session, role_ids)
    return [
        _role_directory_read(
            role,
            user_count=user_counts.get(role.id, 0),
            assignment_field_count=field_counts.get(role.id, 0),
        )
        for role in roles
    ]


@roles_router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def add_role(
    data: RoleCreate,
    session: DatabaseSession,
    principal: Authenticated,
) -> RoleRead:
    try:
        role = create_role(
            session,
            name=data.name,
            description=data.description,
            permissions=data.permissions,
            employee_scope=data.employee_scope,
            assignment_field_scope=data.assignment_field_scope,
            assignment_field_ids=data.assignment_field_ids,
            actor=principal.subject,
        )
    except ValueError as exc:
        _raise_role_value_error(exc)
    return _role_read(session, role)


@roles_router.get("/{role_id}", response_model=RoleRead)
def get_role(role_id: int, session: DatabaseSession) -> RoleRead:
    return _role_read(session, _find_role(session, role_id))


@roles_router.patch("/{role_id}", response_model=RoleRead)
def change_role(
    role_id: int,
    data: RoleUpdate,
    session: DatabaseSession,
    principal: Authenticated,
) -> RoleRead:
    role = _find_role(session, role_id)
    try:
        role = update_role(
            session,
            role,
            name=data.name,
            description=data.description
            if "description" in data.model_fields_set
            else None,
            permissions=data.permissions,
            employee_scope=data.employee_scope,
            assignment_field_scope=data.assignment_field_scope,
            assignment_field_ids=data.assignment_field_ids,
            description_supplied="description" in data.model_fields_set,
            actor=principal.subject,
        )
    except ValueError as exc:
        _raise_role_value_error(exc)
    return _role_read(session, role)


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_role(
    role_id: int,
    session: DatabaseSession,
    principal: Authenticated,
) -> Response:
    try:
        delete_role(session, _find_role(session, role_id), actor=principal.subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.get("", response_model=list[UserDirectoryRead])
def list_users(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    visibility: EmployeeScope,
    search: Annotated[str | None, Query(max_length=200)] = None,
    user_status: Annotated[
        Literal["active", "suspended", "disabled"] | None,
        Query(alias="status"),
    ] = None,
    role_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[UserDirectoryRead]:
    statement = select(User).options(
        load_only(
            User.id,
            User.email,
            User.name,
            User.status,
            User.is_root,
            User.password_change_required,
            User.employee_id,
        ),
        selectinload(User.roles)
        .load_only(Role.id, Role.name)
        .selectinload(Role.role_permissions)
        .load_only(RolePermission.permission),
    )
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(User.name.ilike(pattern), User.email.ilike(pattern))
        )
    if user_status:
        statement = statement.where(User.status == user_status)
    if role_id:
        statement = statement.where(User.roles.any(Role.id == role_id))
    users = paginate_scalars(
        session, statement.order_by(User.name, User.id), pagination, response
    )
    employee_ids = {
        user.employee_id
        for user in users
        if user.employee_id is not None and visibility.can_access(user.employee_id)
    }
    employees = {
        employee_id: EmployeeLinkSummaryRead(
            id=employee_id,
            name=name,
            department=department,
        )
        for employee_id, name, department in session.execute(
            select(Employee.id, Employee.name, Employee.department).where(
                Employee.id.in_(employee_ids)
            )
        ).all()
    }
    return [_user_directory_read(user, visibility, employees) for user in users]


@users_router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def add_user(
    data: UserCreate,
    session: DatabaseSession,
    principal: Authenticated,
    visibility: EmployeeScope,
) -> UserRead:
    if data.employee_id is not None:
        visible_employee_or_404(session, visibility, data.employee_id)
    try:
        user = create_user(
            session,
            name=data.name,
            email=str(data.email),
            password=data.temporary_password,
            role_ids=data.role_ids,
            employee_id=data.employee_id,
            actor=principal.subject,
        )
    except ValueError as exc:
        _raise_user_value_error(exc)
    return _user_read(session, user, visibility)


@users_router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    session: DatabaseSession,
    visibility: EmployeeScope,
) -> UserRead:
    return _user_read(session, _find_user(session, user_id), visibility)


@users_router.patch("/{user_id}", response_model=UserRead)
def change_user(
    user_id: int,
    data: UserUpdate,
    session: DatabaseSession,
    principal: Authenticated,
    visibility: EmployeeScope,
) -> UserRead:
    if principal.user_id is None:
        actor_user_id = -1
    else:
        actor_user_id = principal.user_id
    user = _find_user(session, user_id)
    if "employee_id" in data.model_fields_set:
        if user.employee_id is not None:
            visible_employee_or_404(session, visibility, user.employee_id)
        if data.employee_id is not None:
            visible_employee_or_404(session, visibility, data.employee_id)
    try:
        user = update_user(
            session,
            user,
            name=data.name,
            status=data.status,
            role_ids=data.role_ids,
            employee_id=data.employee_id,
            employee_id_supplied="employee_id" in data.model_fields_set,
            actor=principal.subject,
            actor_user_id=actor_user_id,
        )
    except ValueError as exc:
        _raise_user_value_error(exc)
    return _user_read(session, user, visibility)


@users_router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_password(
    user_id: int,
    data: UserPasswordResetCreate,
    session: DatabaseSession,
    principal: Authenticated,
    visibility: EmployeeScope,
) -> UserRead:
    user = _find_user(session, user_id)
    try:
        reset_user_password(
            session,
            user,
            password=data.temporary_password,
            actor=principal.subject,
        )
    except ValueError as exc:
        _raise_user_value_error(exc)
    return _user_read(session, user, visibility)


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(
    user_id: int,
    session: DatabaseSession,
    principal: Authenticated,
) -> Response:
    try:
        disable_user(
            session,
            _find_user(session, user_id),
            actor=principal.subject,
            actor_user_id=principal.user_id or -1,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _role_read(session: DatabaseSession, role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        employee_scope=role.employee_scope,
        assignment_field_scope=role.assignment_field_scope,
        assignment_field_ids=sorted(
            link.assignment_field_definition_id for link in role.assignment_field_links
        ),
        permissions=sorted(link.permission for link in role.role_permissions),
        user_count=_role_user_counts(session, [role.id]).get(role.id, 0),
        created_by=role.created_by,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _role_directory_read(
    role: Role,
    *,
    user_count: int,
    assignment_field_count: int,
) -> RoleDirectoryRead:
    permission_names = sorted(link.permission for link in role.role_permissions)
    return RoleDirectoryRead(
        id=role.id,
        name=role.name,
        description=role.description,
        employee_scope=role.employee_scope,
        assignment_field_scope=role.assignment_field_scope,
        assignment_field_count=assignment_field_count,
        permission_count=len(permission_names),
        permission_preview=[
            PERMISSIONS.get(permission, ("", permission, ""))[1]
            for permission in permission_names[:5]
        ],
        user_count=user_count,
    )


def _role_user_counts(session: DatabaseSession, role_ids: list[int]) -> dict[int, int]:
    if not role_ids:
        return {}
    return {
        role_id: int(count)
        for role_id, count in session.execute(
            select(UserRole.role_id, func.count(UserRole.user_id))
            .where(UserRole.role_id.in_(role_ids))
            .group_by(UserRole.role_id)
        ).all()
    }


def _role_assignment_field_counts(
    session: DatabaseSession, role_ids: list[int]
) -> dict[int, int]:
    if not role_ids:
        return {}
    return {
        role_id: int(count)
        for role_id, count in session.execute(
            select(
                RoleAssignmentFieldScope.role_id,
                func.count(RoleAssignmentFieldScope.assignment_field_definition_id),
            )
            .where(RoleAssignmentFieldScope.role_id.in_(role_ids))
            .group_by(RoleAssignmentFieldScope.role_id)
        ).all()
    }


def _user_directory_read(
    user: User,
    visibility: EmployeeVisibility,
    employees: dict[int, EmployeeLinkSummaryRead],
) -> UserDirectoryRead:
    permissions = (
        {"*"}
        if user.is_root
        else {
            permission.permission
            for role in user.roles
            for permission in role.role_permissions
        }
    )
    employee_visible = user.employee_id is not None and visibility.can_access(
        user.employee_id
    )
    return UserDirectoryRead(
        id=user.id,
        email=user.email,
        name=user.name,
        status=user.status,
        is_root=user.is_root,
        password_change_required=user.password_change_required,
        employee=employees.get(user.employee_id) if employee_visible else None,
        employee_link_hidden=user.employee_id is not None and not employee_visible,
        roles=[
            RoleSummaryRead.model_validate(role)
            for role in sorted(user.roles, key=lambda item: item.name)
        ],
        effective_permission_count=len(permissions),
        has_all_permissions="*" in permissions,
    )


def _user_read(
    session: DatabaseSession,
    user: User,
    visibility: EmployeeVisibility,
) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        status=user.status,
        is_root=user.is_root,
        password_change_required=user.password_change_required,
        mfa_enabled=user.mfa_enabled,
        employee_id=(
            user.employee_id
            if user.employee_id is None or visibility.can_access(user.employee_id)
            else None
        ),
        employee_link_hidden=(
            user.employee_id is not None and not visibility.can_access(user.employee_id)
        ),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        roles=[
            RoleSummaryRead.model_validate(role)
            for role in sorted(user.roles, key=lambda item: item.name)
        ],
        permissions=sorted(effective_permissions(session, user)),
    )


def _find_role(session: DatabaseSession, role_id: int) -> Role:
    try:
        return role_by_id(session, role_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


def _find_user(session: DatabaseSession, user_id: int) -> User:
    try:
        return user_by_id(session, user_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


def _raise_role_value_error(exc: ValueError) -> None:
    code = (
        status.HTTP_409_CONFLICT
        if "already exists" in str(exc)
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    raise HTTPException(status_code=code, detail=str(exc)) from exc


def _raise_user_value_error(exc: ValueError) -> None:
    message = str(exc)
    code = (
        status.HTTP_409_CONFLICT
        if "already exists" in message or "already linked" in message
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    raise HTTPException(status_code=code, detail=message) from exc
