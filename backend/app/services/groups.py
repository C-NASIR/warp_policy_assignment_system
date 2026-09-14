from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.dates import current_datetime
from app.models import (
    Employee,
    EmployeeGroupMembership,
    Group,
    GroupPolicy,
    Policy,
    PolicyVersion,
)
from app.services.audit import record_audit_log, snapshot_entity
from app.services.reconciliation import reconcile_employees


class GroupResourceNotFoundError(ValueError):
    pass


def create_group(session: Session, name: str, actor: str = "system") -> Group:
    group = Group(name=name)
    session.add(group)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="Group",
        entity_id=group.id,
        action="created",
        before=None,
        after=snapshot_entity(group),
    )
    return group


def list_groups(session: Session) -> list[Group]:
    return list(session.scalars(select(Group).order_by(Group.id)))


def get_group(session: Session, group_id: int) -> Group:
    group = session.get(Group, group_id)
    if group is None:
        raise GroupResourceNotFoundError(f"Group {group_id} not found")
    return group


def update_group(
    session: Session,
    group_id: int,
    name: str | None,
    actor: str = "system",
) -> Group:
    group = get_group(session, group_id)
    if name is not None and name != group.name:
        before = snapshot_entity(group)
        group.name = name
        session.flush()
        record_audit_log(
            session,
            actor=actor,
            entity_type="Group",
            entity_id=group.id,
            action="changed",
            before=before,
            after=snapshot_entity(group),
        )
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


def add_employee_to_group(
    session: Session,
    group_id: int,
    employee_id: int,
    actor: str = "system",
) -> Employee:
    get_group(session, group_id)
    employee = _get_employee(session, employee_id)
    key = {"employee_id": employee_id, "group_id": group_id}
    if session.get(EmployeeGroupMembership, key) is None:
        session.add(EmployeeGroupMembership(**key))
        session.flush()
        record_audit_log(
            session,
            actor=actor,
            entity_type="Group",
            entity_id=group_id,
            action="employee_added",
            before=None,
            after=key,
        )
        _refresh_employee(session, employee)
    return employee


def remove_employee_from_group(
    session: Session,
    group_id: int,
    employee_id: int,
    actor: str = "system",
) -> None:
    get_group(session, group_id)
    employee = _get_employee(session, employee_id)
    membership = session.get(
        EmployeeGroupMembership,
        {"employee_id": employee_id, "group_id": group_id},
    )
    if membership is not None:
        before = {"employee_id": employee_id, "group_id": group_id}
        session.delete(membership)
        session.flush()
        record_audit_log(
            session,
            actor=actor,
            entity_type="Group",
            entity_id=group_id,
            action="employee_removed",
            before=before,
            after=None,
        )
        _refresh_employee(session, employee)


def list_group_policies(session: Session, group_id: int) -> list[Policy]:
    get_group(session, group_id)
    return list(
        session.scalars(
            select(Policy)
            .join(GroupPolicy, GroupPolicy.policy_id == Policy.id)
            .where(GroupPolicy.group_id == group_id)
            .options(
                selectinload(Policy.versions).selectinload(PolicyVersion.values)
            )
            .order_by(Policy.id)
        )
    )


def add_policy_to_group(
    session: Session,
    group_id: int,
    policy_id: int,
    actor: str = "system",
) -> Policy:
    get_group(session, group_id)
    policy = _get_policy(session, policy_id)
    key = {"group_id": group_id, "policy_id": policy_id}
    if session.get(GroupPolicy, key) is None:
        _attach_policy(session, key, actor)
        _refresh_group_members(session, group_id)
    return policy


def remove_policy_from_group(
    session: Session,
    group_id: int,
    policy_id: int,
    actor: str = "system",
) -> None:
    get_group(session, group_id)
    _get_policy(session, policy_id)
    group_policy = session.get(
        GroupPolicy,
        {"group_id": group_id, "policy_id": policy_id},
    )
    if group_policy is not None:
        _detach_policy(session, group_policy, actor)
        _refresh_group_members(session, group_id)


def update_group_policies(
    session: Session,
    group_id: int,
    add_policy_ids: list[int],
    remove_policy_ids: list[int],
    actor: str = "system",
) -> None:
    get_group(session, group_id)
    policy_ids = {*add_policy_ids, *remove_policy_ids}
    for policy_id in policy_ids:
        _get_policy(session, policy_id)

    changed = False
    for policy_id in remove_policy_ids:
        group_policy = session.get(
            GroupPolicy,
            {"group_id": group_id, "policy_id": policy_id},
        )
        if group_policy is not None:
            _detach_policy(session, group_policy, actor)
            changed = True

    for policy_id in add_policy_ids:
        key = {"group_id": group_id, "policy_id": policy_id}
        if session.get(GroupPolicy, key) is None:
            _attach_policy(session, key, actor)
            changed = True

    if changed:
        _refresh_group_members(session, group_id)


def _attach_policy(session: Session, key: dict[str, int], actor: str) -> None:
    session.add(GroupPolicy(**key))
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="Group",
        entity_id=key["group_id"],
        action="policy_attached",
        before=None,
        after=key,
    )


def _detach_policy(session: Session, group_policy: GroupPolicy, actor: str) -> None:
    before = {
        "group_id": group_policy.group_id,
        "policy_id": group_policy.policy_id,
    }
    session.delete(group_policy)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="Group",
        entity_id=before["group_id"],
        action="policy_detached",
        before=before,
        after=None,
    )


def _get_employee(session: Session, employee_id: int) -> Employee:
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise GroupResourceNotFoundError(f"Employee {employee_id} not found")
    return employee


def _get_policy(session: Session, policy_id: int) -> Policy:
    policy = session.scalar(
        select(Policy)
        .where(Policy.id == policy_id)
        .options(selectinload(Policy.versions).selectinload(PolicyVersion.values))
    )
    if policy is None:
        raise GroupResourceNotFoundError(f"Policy {policy_id} not found")
    return policy


def _refresh_group_members(session: Session, group_id: int) -> None:
    reconciliation_at = current_datetime()
    reconcile_employees(
        session,
        [employee.id for employee in list_group_employees(session, group_id)],
        reconciliation_at,
    )


def _refresh_employee(
    session: Session,
    employee: Employee,
    reconciliation_at: datetime | None = None,
) -> None:
    reconciliation_at = reconciliation_at or current_datetime()
    reconcile_employees(session, [employee.id], reconciliation_at)
