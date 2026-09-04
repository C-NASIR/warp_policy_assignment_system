from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.dependencies import (
    AssignmentFieldScope,
    AuditActor,
    DatabaseSession,
    EmployeeScope,
)
from app.models import (
    Employee,
    EmployeeGroupMembership,
    Group,
    GroupPolicy,
    Policy,
    PolicyVersion,
)
from app.pagination import Pagination, paginate_scalars
from app.schemas import EmployeeRead, GroupCreate, GroupRead, GroupUpdate, PolicyRead
from app.services.assignment_field_visibility import (
    require_visible_policy,
    visible_policy_condition,
)
from app.services.employee_visibility import visible_employee_or_404
from app.services.groups import (
    add_employee_to_group,
    add_policy_to_group,
    create_group,
    get_group,
    remove_employee_from_group,
    remove_policy_from_group,
    update_group,
)

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create(data: GroupCreate, session: DatabaseSession, actor: AuditActor) -> Group:
    return create_group(session, data.name, actor)


@router.get("", response_model=list[GroupRead])
def list_all(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> list[Group]:
    statement = select(Group)
    if search:
        statement = statement.where(Group.name.ilike(f"%{search.strip()}%"))
    return paginate_scalars(
        session,
        statement.order_by(Group.id),
        pagination,
        response,
    )


@router.get("/{group_id}", response_model=GroupRead)
def get(group_id: int, session: DatabaseSession) -> Group:
    return get_group(session, group_id)


@router.patch("/{group_id}", response_model=GroupRead)
def patch(
    group_id: int,
    data: GroupUpdate,
    session: DatabaseSession,
    actor: AuditActor,
) -> Group:
    return update_group(session, group_id, data.name, actor)


@router.get("/{group_id}/employees", response_model=list[EmployeeRead])
def employees(
    group_id: int,
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    visibility: EmployeeScope,
    search: Annotated[str | None, Query(max_length=200)] = None,
    state: Annotated[str | None, Query(max_length=100)] = None,
    department: Annotated[str | None, Query(max_length=100)] = None,
    employee_type: Annotated[str | None, Query(max_length=100)] = None,
) -> list[Employee]:
    get_group(session, group_id)
    statement = (
        select(Employee)
        .join(
            EmployeeGroupMembership,
            EmployeeGroupMembership.employee_id == Employee.id,
        )
        .where(EmployeeGroupMembership.group_id == group_id)
    )
    statement = visibility.apply(statement)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Employee.name.ilike(pattern),
                Employee.state.ilike(pattern),
                Employee.department.ilike(pattern),
                Employee.employee_type.ilike(pattern),
            )
        )
    if state is not None:
        statement = statement.where(Employee.state == state)
    if department is not None:
        statement = statement.where(Employee.department == department)
    if employee_type is not None:
        statement = statement.where(Employee.employee_type == employee_type)
    return paginate_scalars(
        session,
        statement.order_by(Employee.id),
        pagination,
        response,
    )


@router.post(
    "/{group_id}/employees/{employee_id}",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
)
def add_employee(
    group_id: int,
    employee_id: int,
    session: DatabaseSession,
    actor: AuditActor,
    visibility: EmployeeScope,
) -> Employee:
    visible_employee_or_404(session, visibility, employee_id)
    return add_employee_to_group(session, group_id, employee_id, actor)


@router.delete(
    "/{group_id}/employees/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_employee(
    group_id: int,
    employee_id: int,
    session: DatabaseSession,
    actor: AuditActor,
    visibility: EmployeeScope,
) -> Response:
    visible_employee_or_404(session, visibility, employee_id)
    remove_employee_from_group(session, group_id, employee_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{group_id}/policies", response_model=list[PolicyRead])
def policies(
    group_id: int,
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    field_visibility: AssignmentFieldScope,
    search: Annotated[str | None, Query(max_length=200)] = None,
    status_filter: Annotated[
        Literal["active", "archived"] | None,
        Query(alias="status"),
    ] = None,
) -> list[Policy]:
    get_group(session, group_id)
    statement = (
        select(Policy)
        .join(GroupPolicy, GroupPolicy.policy_id == Policy.id)
        .where(GroupPolicy.group_id == group_id)
        .where(visible_policy_condition(field_visibility))
        .options(selectinload(Policy.versions).selectinload(PolicyVersion.values))
    )
    if search:
        statement = statement.where(Policy.name.ilike(f"%{search.strip()}%"))
    if status_filter is not None:
        statement = statement.where(Policy.status == status_filter)
    return paginate_scalars(
        session,
        statement.order_by(Policy.id),
        pagination,
        response,
    )


@router.post(
    "/{group_id}/policies/{policy_id}",
    response_model=PolicyRead,
    status_code=status.HTTP_201_CREATED,
)
def add_policy(
    group_id: int,
    policy_id: int,
    session: DatabaseSession,
    actor: AuditActor,
    field_visibility: AssignmentFieldScope,
) -> Policy:
    require_visible_policy(session, field_visibility, policy_id)
    return add_policy_to_group(session, group_id, policy_id, actor)


@router.delete(
    "/{group_id}/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_policy(
    group_id: int,
    policy_id: int,
    session: DatabaseSession,
    actor: AuditActor,
    field_visibility: AssignmentFieldScope,
) -> Response:
    require_visible_policy(session, field_visibility, policy_id)
    remove_policy_from_group(session, group_id, policy_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
