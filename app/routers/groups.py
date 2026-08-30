from fastapi import APIRouter, Response, status

from app.dependencies import AuditActor, DatabaseSession
from app.models import Employee, Group, Policy
from app.schemas import EmployeeRead, GroupCreate, GroupRead, GroupUpdate, PolicyRead
from app.services.groups import (
    add_employee_to_group,
    add_policy_to_group,
    create_group,
    get_group,
    list_group_employees,
    list_group_policies,
    list_groups,
    remove_employee_from_group,
    remove_policy_from_group,
    update_group,
)

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create(data: GroupCreate, session: DatabaseSession, actor: AuditActor) -> Group:
    return create_group(session, data.name, actor)


@router.get("", response_model=list[GroupRead])
def list_all(session: DatabaseSession) -> list[Group]:
    return list_groups(session)


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
def employees(group_id: int, session: DatabaseSession) -> list[Employee]:
    return list_group_employees(session, group_id)


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
) -> Employee:
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
) -> Response:
    remove_employee_from_group(session, group_id, employee_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{group_id}/policies", response_model=list[PolicyRead])
def policies(group_id: int, session: DatabaseSession) -> list[Policy]:
    return list_group_policies(session, group_id)


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
) -> Policy:
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
) -> Response:
    remove_policy_from_group(session, group_id, policy_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
