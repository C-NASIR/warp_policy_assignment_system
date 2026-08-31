from __future__ import annotations

from collections.abc import Collection
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dates import current_datetime, ensure_utc, start_of_day
from app.models import (
    Employee,
    EmployeeOverride,
    Policy,
    PolicyVersion,
    ScheduledReconciliation,
)
from app.services.policy_reconciliation import refresh_employees_affected_by_policy
from app.services.reconciliation import (
    reconcile_employees,
    refresh_employee_assignments,
)

POLICY_VERSION_ENTITY = "PolicyVersion"
EMPLOYEE_ENTITY = "Employee"
EMPLOYEE_OVERRIDE_ENTITY = "EmployeeOverride"

BECOMES_EFFECTIVE_TRIGGER = "becomes_effective"
EXPIRES_TRIGGER = "expires"
TENURE_THRESHOLD_TRIGGER = "tenure_threshold"

_SUPPORTED_TRIGGERS = {
    POLICY_VERSION_ENTITY: {BECOMES_EFFECTIVE_TRIGGER, EXPIRES_TRIGGER},
    EMPLOYEE_ENTITY: {TENURE_THRESHOLD_TRIGGER},
    EMPLOYEE_OVERRIDE_ENTITY: {BECOMES_EFFECTIVE_TRIGGER, EXPIRES_TRIGGER},
}


class ScheduledReconciliationError(ValueError):
    pass


class ScheduledReconciliationEntityNotFoundError(ScheduledReconciliationError):
    pass


def schedule_reconciliation(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    trigger_type: str,
    scheduled_at: datetime,
) -> ScheduledReconciliation:
    """Create an event idempotently, restoring a cancelled event if necessary."""
    _validate_event(entity_type, entity_id, trigger_type)
    scheduled_at = ensure_utc(scheduled_at)
    event = session.scalar(
        select(ScheduledReconciliation).where(
            ScheduledReconciliation.entity_type == entity_type,
            ScheduledReconciliation.entity_id == entity_id,
            ScheduledReconciliation.trigger_type == trigger_type,
            ScheduledReconciliation.scheduled_at == scheduled_at,
        )
    )
    if event is None:
        event = ScheduledReconciliation(
            entity_type=entity_type,
            entity_id=entity_id,
            trigger_type=trigger_type,
            scheduled_at=scheduled_at,
        )
        session.add(event)
        session.flush()
    elif event.status == "cancelled":
        event.status = "pending"
        session.flush()
    return event


def cancel_pending_reconciliations(
    session: Session,
    *,
    entity_type: str,
    entity_ids: Collection[int],
    keep: Collection[tuple[int, str, datetime]] = (),
) -> list[ScheduledReconciliation]:
    """Cancel pending events for entities except the exact desired event keys."""
    ids = set(entity_ids)
    if not ids:
        return []
    keep_keys = {
        (entity_id, trigger_type, ensure_utc(scheduled_at))
        for entity_id, trigger_type, scheduled_at in keep
    }
    events = list(
        session.scalars(
            select(ScheduledReconciliation).where(
                ScheduledReconciliation.entity_type == entity_type,
                ScheduledReconciliation.entity_id.in_(ids),
                ScheduledReconciliation.status == "pending",
            )
        )
    )
    cancelled: list[ScheduledReconciliation] = []
    for event in events:
        key = (
            event.entity_id,
            event.trigger_type,
            ensure_utc(event.scheduled_at),
        )
        if key not in keep_keys:
            event.status = "cancelled"
            cancelled.append(event)
    session.flush()
    return cancelled


def sync_policy_version_schedules(
    session: Session,
    policy: Policy,
    *,
    as_of: datetime | None = None,
) -> list[ScheduledReconciliation]:
    """Make future policy-version events match the policy's current date ranges."""
    now = ensure_utc(as_of or current_datetime())
    session.flush()
    versions = list(
        session.scalars(
            select(PolicyVersion)
            .where(PolicyVersion.policy_id == policy.id)
            .order_by(PolicyVersion.version_number)
        )
    )
    desired: dict[tuple[int, str, datetime], None] = {}
    if policy.status == "active":
        for version in versions:
            becomes_effective_at = start_of_day(version.effective_from)
            if becomes_effective_at > now:
                desired[(version.id, BECOMES_EFFECTIVE_TRIGGER, becomes_effective_at)] = None
            if version.effective_until is not None and version.effective_until < date.max:
                expires_at = start_of_day(version.effective_until + timedelta(days=1))
                if expires_at > now:
                    desired[(version.id, EXPIRES_TRIGGER, expires_at)] = None

    cancel_pending_reconciliations(
        session,
        entity_type=POLICY_VERSION_ENTITY,
        entity_ids=[version.id for version in versions],
        keep=desired,
    )
    scheduled = [
        schedule_reconciliation(
            session,
            entity_type=POLICY_VERSION_ENTITY,
            entity_id=entity_id,
            trigger_type=trigger_type,
            scheduled_at=scheduled_at,
        )
        for entity_id, trigger_type, scheduled_at in desired
    ]
    return sorted(scheduled, key=lambda event: (event.scheduled_at, event.id))


def get_due_reconciliations(
    session: Session,
    *,
    as_of: datetime | None = None,
    limit: int = 100,
    lock: bool = False,
) -> list[ScheduledReconciliation]:
    """Return pending events due by one UTC instant in deterministic order."""
    if limit < 1:
        raise ValueError("limit must be positive")
    due_at = ensure_utc(as_of or current_datetime())
    statement = (
        select(ScheduledReconciliation)
        .where(
            ScheduledReconciliation.status == "pending",
            ScheduledReconciliation.scheduled_at <= due_at,
        )
        .order_by(
            ScheduledReconciliation.scheduled_at,
            ScheduledReconciliation.id,
        )
        .limit(limit)
    )
    if lock:
        statement = statement.with_for_update(skip_locked=True)
    return list(session.scalars(statement))


def reconcile_due_events(
    session: Session,
    *,
    as_of: datetime | None = None,
    limit: int = 100,
) -> list[ScheduledReconciliation]:
    """Process one due batch; a future worker can call this transactionally."""
    processed_at = ensure_utc(as_of or current_datetime())
    events = get_due_reconciliations(
        session,
        as_of=processed_at,
        limit=limit,
        lock=True,
    )
    policies: dict[int, Policy] = {}
    employees: dict[int, Employee] = {}
    override_employees: dict[int, Employee] = {}

    for event in events:
        _validate_event(event.entity_type, event.entity_id, event.trigger_type)
        if event.entity_type == POLICY_VERSION_ENTITY:
            version = session.get(PolicyVersion, event.entity_id)
            if version is None:
                raise ScheduledReconciliationEntityNotFoundError(
                    f"PolicyVersion {event.entity_id} not found"
                )
            policies[version.policy_id] = version.policy
        elif event.entity_type == EMPLOYEE_ENTITY:
            employee = session.get(Employee, event.entity_id)
            if employee is None:
                raise ScheduledReconciliationEntityNotFoundError(
                    f"Employee {event.entity_id} not found"
                )
            employees[employee.id] = employee
        elif event.entity_type == EMPLOYEE_OVERRIDE_ENTITY:
            override = session.get(EmployeeOverride, event.entity_id)
            if override is None:
                raise ScheduledReconciliationEntityNotFoundError(
                    f"EmployeeOverride {event.entity_id} not found"
                )
            override_employees[override.employee_id] = override.employee
        else:
            raise ScheduledReconciliationError(
                f"Unsupported scheduled reconciliation entity type: {event.entity_type}"
            )

    for policy_id in sorted(policies):
        refresh_employees_affected_by_policy(
            session,
            policies[policy_id],
            processed_at,
        )
    for employee_id in sorted(employees):
        _refresh_employee(session, employees[employee_id], processed_at)
    for employee_id in sorted(override_employees):
        if employee_id in employees:
            continue
        refresh_employee_assignments(
            session,
            override_employees[employee_id],
            processed_at.date(),
            processed_at,
        )

    for event in events:
        event.status = "processed"
        event.processed_at = processed_at
    session.flush()
    return events


def _refresh_employee(
    session: Session,
    employee: Employee,
    reconciliation_at: datetime,
) -> None:
    reconcile_employees(session, [employee.id], reconciliation_at)


def _validate_event(entity_type: str, entity_id: int, trigger_type: str) -> None:
    if entity_id <= 0:
        raise ScheduledReconciliationError("entity_id must be positive")
    supported = _SUPPORTED_TRIGGERS.get(entity_type)
    if supported is None:
        raise ScheduledReconciliationError(
            f"Unsupported scheduled reconciliation entity type: {entity_type}"
        )
    if trigger_type not in supported:
        raise ScheduledReconciliationError(
            f"Unsupported trigger '{trigger_type}' for {entity_type}"
        )
