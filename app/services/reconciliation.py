from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dates import current_datetime, ensure_utc, start_of_day
from app.models import Employee, EmployeeAssignment, EmployeeOverride, AssignmentFieldDefinition
from app.services.audit import record_audit_log, snapshot_assignment
from app.services.overrides import FinalAssignment, apply_employee_overrides
from app.services.policy_engine import resolve_employee_assignments


class AssignmentReconciliationOrderError(ValueError):
    pass


def refresh_employee_assignments(
    session: Session,
    employee: Employee,
    evaluation_date: date | None = None,
    reconciliation_at: datetime | None = None,
    actor: str = "system",
) -> list[EmployeeAssignment]:
    effective_at = _reconciliation_timestamp(evaluation_date, reconciliation_at)
    policy_evaluation_date = evaluation_date or effective_at.date()
    _reject_out_of_order_reconciliation(session, employee.id, effective_at)
    resolved_assignments = resolve_employee_assignments(
        session,
        employee,
        policy_evaluation_date,
    )
    overrides = list(
        session.scalars(
            select(EmployeeOverride)
            .where(
                EmployeeOverride.employee_id == employee.id,
                EmployeeOverride.retired_at.is_(None),
            )
            .order_by(
                EmployeeOverride.assignment_field_definition_id,
                EmployeeOverride.value,
                EmployeeOverride.id,
            )
        )
    )
    final_assignments = apply_employee_overrides(resolved_assignments, overrides)
    current_assignments = list(
        session.scalars(
            select(EmployeeAssignment)
            .where(
                EmployeeAssignment.employee_id == employee.id,
                EmployeeAssignment.effective_until.is_(None),
            )
            .with_for_update()
        )
    )
    desired_by_key = {_assignment_key(item): item for item in final_assignments}
    active_assignments: list[EmployeeAssignment] = []
    field_names = {
        field.id: field.name
        for field in session.scalars(
            select(AssignmentFieldDefinition).where(
                AssignmentFieldDefinition.id.in_(
                    {
                        *[item.assignment_field_definition_id for item in current_assignments],
                        *[item.assignment_field_definition_id for item in final_assignments],
                    }
                )
            )
        )
    }

    for assignment in current_assignments:
        if desired_by_key.pop(_assignment_key(assignment), None) is not None:
            active_assignments.append(assignment)
            continue
        before = snapshot_assignment(
            assignment,
            field_name=field_names.get(assignment.assignment_field_definition_id),
        )
        if ensure_utc(assignment.effective_from) == effective_at:
            session.delete(assignment)
        else:
            assignment.effective_until = effective_at
        record_audit_log(
            session,
            actor=actor,
            entity_type="EmployeeAssignment",
            entity_id=assignment.id,
            action="ended",
            before=before,
            after=None,
            timestamp=effective_at,
        )

    for item in desired_by_key.values():
        assignment = EmployeeAssignment(
            employee_id=employee.id,
            assignment_field_definition_id=item.assignment_field_definition_id,
            value=item.value,
            source_policy_version_id=item.source_policy_version_id,
            source_override_id=item.source_override_id,
            effective_from=effective_at,
        )
        session.add(assignment)
        session.flush()
        record_audit_log(
            session,
            actor=actor,
            entity_type="EmployeeAssignment",
            entity_id=assignment.id,
            action="created",
            before=None,
            after=snapshot_assignment(
                assignment,
                field_name=field_names.get(assignment.assignment_field_definition_id),
            ),
            timestamp=effective_at,
        )
        active_assignments.append(assignment)

    session.flush()
    session.expire(employee, ["assignments"])
    return sorted(
        active_assignments,
        key=lambda item: (item.assignment_field_definition_id, item.value, item.id),
    )


def _reconciliation_timestamp(
    evaluation_date: date | None,
    reconciliation_at: datetime | None,
) -> datetime:
    if reconciliation_at is not None:
        return ensure_utc(reconciliation_at)
    if evaluation_date is not None:
        return start_of_day(evaluation_date)
    return current_datetime()


def _reject_out_of_order_reconciliation(
    session: Session,
    employee_id: int,
    reconciliation_at: datetime,
) -> None:
    latest_start = session.scalar(
        select(func.max(EmployeeAssignment.effective_from)).where(
            EmployeeAssignment.employee_id == employee_id
        )
    )
    if latest_start is not None and reconciliation_at < ensure_utc(latest_start):
        raise AssignmentReconciliationOrderError(
            "Assignment reconciliation cannot run before existing assignment history"
        )


def _assignment_key(
    assignment: EmployeeAssignment | FinalAssignment,
) -> tuple[int, str, int | None, int | None]:
    return (
        assignment.assignment_field_definition_id,
        assignment.value,
        assignment.source_policy_version_id,
        assignment.source_override_id,
    )
