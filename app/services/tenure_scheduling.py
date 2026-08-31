from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dates import current_datetime, ensure_utc, start_of_day
from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    ConditionFieldDefinition,
    Employee,
    Policy,
    PolicyVersion,
    ScheduledReconciliation,
)
from app.services.condition_fields import tenure_transition_dates
from app.services.scheduled_reconciliations import (
    EMPLOYEE_ENTITY,
    TENURE_THRESHOLD_TRIGGER,
    cancel_pending_reconciliations,
    schedule_reconciliation,
)


def sync_employee_tenure_schedules(
    session: Session,
    employee: Employee,
    *,
    as_of: datetime | None = None,
) -> list[ScheduledReconciliation]:
    """Make one employee's pending tenure events match all active policy rules."""
    now = ensure_utc(as_of or current_datetime())
    session.flush()
    conditions = list(
        session.scalars(
            select(CompiledPolicyCondition)
            .join(CompiledPolicyCondition.condition_field_definition)
            .join(CompiledPolicyCondition.clause)
            .join(CompiledPolicyClause.policy_version)
            .join(PolicyVersion.policy)
            .where(
                ConditionFieldDefinition.key == "tenure",
                ConditionFieldDefinition.active.is_(True),
                Policy.status == "active",
            )
            .options(
                joinedload(CompiledPolicyCondition.clause).joinedload(
                    CompiledPolicyClause.policy_version
                )
            )
            .order_by(CompiledPolicyCondition.id)
        )
    )
    desired: dict[tuple[int, str, datetime], None] = {}
    for condition in conditions:
        version = condition.clause.policy_version
        for transition_date in tenure_transition_dates(
            employee.start_date,
            condition.operator,
            condition.value,
        ):
            if transition_date < version.effective_from:
                continue
            if (
                version.effective_until is not None
                and transition_date > version.effective_until
            ):
                continue
            scheduled_at = start_of_day(transition_date)
            if scheduled_at > now:
                desired[(employee.id, TENURE_THRESHOLD_TRIGGER, scheduled_at)] = None

    cancel_pending_reconciliations(
        session,
        entity_type=EMPLOYEE_ENTITY,
        entity_ids=[employee.id],
        keep=desired,
    )
    events = [
        schedule_reconciliation(
            session,
            entity_type=EMPLOYEE_ENTITY,
            entity_id=employee_id,
            trigger_type=trigger_type,
            scheduled_at=scheduled_at,
        )
        for employee_id, trigger_type, scheduled_at in desired
    ]
    return sorted(events, key=lambda event: (event.scheduled_at, event.id))


def sync_all_employee_tenure_schedules(
    session: Session,
    *,
    as_of: datetime | None = None,
) -> list[ScheduledReconciliation]:
    now = ensure_utc(as_of or current_datetime())
    events: list[ScheduledReconciliation] = []
    for employee in session.scalars(select(Employee).order_by(Employee.id)):
        events.extend(sync_employee_tenure_schedules(session, employee, as_of=now))
    return events
