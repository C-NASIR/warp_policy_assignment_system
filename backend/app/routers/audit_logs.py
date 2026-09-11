import re
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.dependencies import AssignmentFieldScope, DatabaseSession, EmployeeScope
from app.models import AuditLog, Employee, Group, Policy, PolicyVersion
from app.pagination import Pagination, paginate_scalars
from app.schemas import AuditLogFacetsRead, AuditLogRead
from app.services.assignment_field_visibility import (
    apply_assignment_field_audit_visibility,
)
from app.services.audit import audit_log_statement
from app.services.employee_visibility import apply_audit_visibility

router = APIRouter(prefix="/audit-logs", tags=["audit logs"])


@router.get("/facets", response_model=AuditLogFacetsRead)
def facets(
    session: DatabaseSession,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
) -> AuditLogFacetsRead:
    def visible_values(column) -> list[str]:
        statement = select(column).distinct()
        statement = apply_audit_visibility(statement, visibility)
        statement = apply_assignment_field_audit_visibility(
            session,
            statement,
            field_visibility,
        )
        return sorted(session.scalars(statement))

    return AuditLogFacetsRead(
        entity_types=visible_values(AuditLog.entity_type),
        actions=visible_values(AuditLog.action),
    )


@router.get("", response_model=list[AuditLogRead])
def list_all(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor: str | None = None,
    action: str | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort: Literal["asc", "desc"] = "asc",
) -> list[AuditLogRead]:
    statement = audit_log_statement(
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        action=action,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        search=search,
    )
    statement = apply_audit_visibility(statement, visibility)
    statement = apply_assignment_field_audit_visibility(
        session,
        statement,
        field_visibility,
    )
    order = (
        (AuditLog.timestamp.desc(), AuditLog.id.desc())
        if sort == "desc"
        else (AuditLog.timestamp, AuditLog.id)
    )
    events = paginate_scalars(
        session,
        statement.order_by(*order),
        pagination,
        response,
    )
    return _with_entity_labels(session, events)


def _with_entity_labels(
    session: DatabaseSession,
    events: list[AuditLog],
) -> list[AuditLogRead]:
    employee_ids: set[int] = set()
    policy_ids: set[int] = set()
    group_ids: set[int] = set()
    policy_version_ids: set[int] = set()
    for event in events:
        snapshot = _snapshot(event)
        employee_id = snapshot.get("employee_id")
        if isinstance(employee_id, int):
            employee_ids.add(employee_id)
        if event.entity_type == "Employee":
            employee_ids.add(event.entity_id)
        elif event.entity_type == "Policy":
            policy_ids.add(event.entity_id)
        elif event.entity_type == "Group":
            group_ids.add(event.entity_id)
        elif event.entity_type == "PolicyVersion":
            policy_version_ids.add(event.entity_id)

    employee_names = dict(
        session.execute(
            select(Employee.id, Employee.name).where(Employee.id.in_(employee_ids))
        ).tuples().all()
    )
    policy_names = dict(
        session.execute(
            select(Policy.id, Policy.name).where(Policy.id.in_(policy_ids))
        ).tuples().all()
    )
    group_names = dict(
        session.execute(
            select(Group.id, Group.name).where(Group.id.in_(group_ids))
        ).tuples().all()
    )
    version_rows = session.execute(
        select(PolicyVersion.id, Policy.name, PolicyVersion.version_number)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
        .where(PolicyVersion.id.in_(policy_version_ids))
    ).all()
    version_names = {
        version_id: f"{policy_name} · Version {version_number}"
        for version_id, policy_name, version_number in version_rows
    }

    return [
        AuditLogRead.model_validate(event).model_copy(
            update={
                "entity_label": _entity_label(
                    event,
                    employee_names,
                    policy_names,
                    group_names,
                    version_names,
                )
            }
        )
        for event in events
    ]


def _snapshot(event: AuditLog) -> dict:
    snapshot: dict = {}
    if isinstance(event.before, dict):
        snapshot.update(event.before)
    if isinstance(event.after, dict):
        snapshot.update(event.after)
    return snapshot


def _entity_label(
    event: AuditLog,
    employee_names: dict[int, str],
    policy_names: dict[int, str],
    group_names: dict[int, str],
    version_names: dict[int, str],
) -> str:
    snapshot = _snapshot(event)
    snapshot_name = snapshot.get("name")
    if event.entity_type == "Employee":
        return employee_names.get(event.entity_id, str(snapshot_name or "Employee"))
    if event.entity_type == "Policy":
        return policy_names.get(event.entity_id, str(snapshot_name or "Policy"))
    if event.entity_type == "Group":
        return group_names.get(event.entity_id, str(snapshot_name or "Group"))
    if event.entity_type == "PolicyVersion":
        return version_names.get(event.entity_id, "Policy version")
    employee_id = snapshot.get("employee_id")
    employee_name = employee_names.get(employee_id) if isinstance(employee_id, int) else None
    suffix = {
        "EmployeeAssignment": "Assignment",
        "EmployeeOverride": "Manual override",
        "EmployeeGroupMembership": "Group membership",
    }.get(event.entity_type)
    if suffix is not None:
        return f"{employee_name} · {suffix}" if employee_name else suffix
    return str(snapshot_name or _humanize_entity_type(event.entity_type))


def _humanize_entity_type(value: str) -> str:
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value).replace("_", " ")
    return words[:1].upper() + words[1:]
