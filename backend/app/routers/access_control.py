from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.dependencies import Authenticated, DatabaseSession, EmployeeScope
from app.models import AssignmentFieldDefinition, AutomatedUserRole, Role, User
from app.pagination import Pagination, paginate_scalars, paginate_sequence
from app.schemas import (
    AssignmentFieldDefinitionRead,
    PermissionRead,
    RoleCreate,
    RoleRead,
    RoleSummaryRead,
    RoleUpdate,
    UserCreate,
    UserPasswordResetCreate,
    UserRead,
    UserUpdate,
)
from app.services.access_control import (
    PERMISSIONS,
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


@authorization_router.get(
    "/assignment-fields",
    response_model=list[AssignmentFieldDefinitionRead],
)
def list_authorization_assignment_fields(
    session: DatabaseSession,
) -> list[AssignmentFieldDefinition]:
    """Expose the field catalog needed to configure role data scopes."""
    return list(
        session.scalars(
            select(AssignmentFieldDefinition).order_by(
                AssignmentFieldDefinition.name,
                AssignmentFieldDefinition.id,
            )
        )
    )


@roles_router.get("", response_model=list[RoleRead])
def list_roles(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> list[RoleRead]:
    statement = select(Role).options(
        selectinload(Role.permission_links),
        selectinload(Role.assignment_field_links),
        selectinload(Role.automated_user_links),
        selectinload(Role.users),
    )
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(Role.name.ilike(pattern), Role.description.ilike(pattern))
        )
    roles = paginate_scalars(session, statement.order_by(Role.name, Role.id), pagination, response)
    return [_role_read(role) for role in roles]


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
            automation_eligible=data.automation_eligible,
            actor=principal.subject,
        )
    except ValueError as exc:
        _raise_role_value_error(exc)
    return _role_read(role)


@roles_router.get("/{role_id}", response_model=RoleRead)
def get_role(role_id: int, session: DatabaseSession) -> RoleRead:
    return _role_read(_find_role(session, role_id))


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
            description=data.description if "description" in data.model_fields_set else None,
            permissions=data.permissions,
            employee_scope=data.employee_scope,
            assignment_field_scope=data.assignment_field_scope,
            assignment_field_ids=data.assignment_field_ids,
            automation_eligible=data.automation_eligible,
            description_supplied="description" in data.model_fields_set,
            actor=principal.subject,
        )
    except ValueError as exc:
        _raise_role_value_error(exc)
    return _role_read(role)


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_role(
    role_id: int,
    session: DatabaseSession,
    principal: Authenticated,
) -> Response:
    try:
        delete_role(session, _find_role(session, role_id), actor=principal.subject)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.get("", response_model=list[UserRead])
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
) -> list[UserRead]:
    statement = select(User).options(
        selectinload(User.roles).selectinload(Role.permission_links)
    )
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    if user_status:
        statement = statement.where(User.status == user_status)
    if role_id:
        statement = statement.where(User.roles.any(Role.id == role_id))
    users = paginate_scalars(session, statement.order_by(User.name, User.id), pagination, response)
    return [_user_read(session, user, visibility) for user in users]


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _role_read(role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        employee_scope=role.employee_scope,
        assignment_field_scope=role.assignment_field_scope,
        assignment_field_ids=sorted(
            link.assignment_field_definition_id
            for link in role.assignment_field_links
        ),
        automation_eligible=role.automation_eligible,
        permissions=sorted(link.permission for link in role.permission_links),
        user_count=len(
            {user.id for user in role.users}
            | {link.user_id for link in role.automated_user_links}
        ),
        created_by=role.created_by,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _user_read(
    session: DatabaseSession,
    user: User,
    visibility: EmployeeVisibility,
) -> UserRead:
    automated_roles = list(
        session.scalars(
            select(Role)
            .join(AutomatedUserRole, AutomatedUserRole.role_id == Role.id)
            .where(AutomatedUserRole.user_id == user.id)
            .distinct()
            .order_by(Role.name)
        )
    )
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        status=user.status,
        is_root=user.is_root,
        password_change_required=user.password_change_required,
        employee_id=(
            user.employee_id
            if user.employee_id is None or visibility.can_access(user.employee_id)
            else None
        ),
        employee_link_hidden=(
            user.employee_id is not None
            and not visibility.can_access(user.employee_id)
        ),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        roles=[RoleSummaryRead.model_validate(role) for role in sorted(user.roles, key=lambda item: item.name)],
        automated_roles=[
            RoleSummaryRead.model_validate(role) for role in automated_roles
        ],
        permissions=sorted(effective_permissions(session, user)),
    )


def _find_role(session: DatabaseSession, role_id: int) -> Role:
    try:
        return role_by_id(session, role_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _find_user(session: DatabaseSession, user_id: int) -> User:
    try:
        return user_by_id(session, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _raise_role_value_error(exc: ValueError) -> None:
    code = status.HTTP_409_CONFLICT if "already exists" in str(exc) else status.HTTP_422_UNPROCESSABLE_CONTENT
    raise HTTPException(status_code=code, detail=str(exc)) from exc


def _raise_user_value_error(exc: ValueError) -> None:
    message = str(exc)
    code = status.HTTP_409_CONFLICT if "already exists" in message or "already linked" in message else status.HTTP_422_UNPROCESSABLE_CONTENT
    raise HTTPException(status_code=code, detail=message) from exc
