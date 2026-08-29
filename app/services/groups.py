from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Employee,
    EmployeeGroupMembership,
    Group,
    GroupPolicy,
    Policy,
)
from app.services.policy_matching import refresh_employee_policies
from app.services.reconciliation import refresh_employee_assignments


class GroupResourceNotFoundError(ValueError):
    pass


def create_group(session: Session, name: str) -> Group:
    group = Group(name=name)
    session.add(group)
    session.flush()
    return group


def list_groups(session: Session) -> list[Group]:
    return list(session.scalars(select(Group).order_by(Group.id)))


def get_group(session: Session, group_id: int) -> Group:
    group = session.get(Group, group_id)
    if group is None:
        raise GroupResourceNotFoundError(f"Group {group_id} not found")
    return group


def update_group(session: Session, group_id: int, name: str | None) -> Group:
    group = get_group(session, group_id)
    if name is not None:
        group.name = name
        session.flush()
    return group


def list_group_employees(session: Session, group_id: int) -> list[Employee]:
    get_group(session, group_id)
    return list(
        session.scalars(
            select(Employee)
            .join(
                EmployeeGroupMembership,
                EmployeeGroupMembership.employee_id == Employee.id,
            )
            .where(EmployeeGroupMembership.group_id == group_id)
            .order_by(Employee.id)
        )
    )


def add_employee_to_group(session: Session, group_id: int, employee_id: int) -> Employee:
    get_group(session, group_id)
    employee = _get_employee(session, employee_id)
    key = {"employee_id": employee_id, "group_id": group_id}
    if session.get(EmployeeGroupMembership, key) is None:
        session.add(EmployeeGroupMembership(**key))
        session.flush()
        _refresh_employee(session, employee)
    return employee


def remove_employee_from_group(session: Session, group_id: int, employee_id: int) -> None:
    get_group(session, group_id)
    employee = _get_employee(session, employee_id)
    membership = session.get(
        EmployeeGroupMembership,
        {"employee_id": employee_id, "group_id": group_id},
    )
    if membership is not None:
        session.delete(membership)
        session.flush()
        _refresh_employee(session, employee)


def list_group_policies(session: Session, group_id: int) -> list[Policy]:
    get_group(session, group_id)
    return list(
        session.scalars(
            select(Policy)
            .join(GroupPolicy, GroupPolicy.policy_id == Policy.id)
            .where(GroupPolicy.group_id == group_id)
            .options(selectinload(Policy.values))
            .order_by(Policy.id)
        )
    )


def add_policy_to_group(session: Session, group_id: int, policy_id: int) -> Policy:
    get_group(session, group_id)
    policy = _get_policy(session, policy_id)
    key = {"group_id": group_id, "policy_id": policy_id}
    if session.get(GroupPolicy, key) is None:
        session.add(GroupPolicy(**key))
        session.flush()
        _refresh_group_members(session, group_id)
    return policy


def remove_policy_from_group(session: Session, group_id: int, policy_id: int) -> None:
    get_group(session, group_id)
    _get_policy(session, policy_id)
    group_policy = session.get(
        GroupPolicy,
        {"group_id": group_id, "policy_id": policy_id},
    )
    if group_policy is not None:
        session.delete(group_policy)
        session.flush()
        _refresh_group_members(session, group_id)


def _get_employee(session: Session, employee_id: int) -> Employee:
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise GroupResourceNotFoundError(f"Employee {employee_id} not found")
    return employee


def _get_policy(session: Session, policy_id: int) -> Policy:
    policy = session.scalar(
        select(Policy)
        .where(Policy.id == policy_id)
        .options(selectinload(Policy.values))
    )
    if policy is None:
        raise GroupResourceNotFoundError(f"Policy {policy_id} not found")
    return policy


def _refresh_group_members(session: Session, group_id: int) -> None:
    for employee in list_group_employees(session, group_id):
        _refresh_employee(session, employee)


def _refresh_employee(session: Session, employee: Employee) -> None:
    refresh_employee_policies(session, employee.id)
    refresh_employee_assignments(session, employee)
