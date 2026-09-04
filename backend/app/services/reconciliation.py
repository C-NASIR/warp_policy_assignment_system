import json
from collections.abc import Collection
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dates import current_datetime, ensure_utc, start_of_day
from app.models import (
    AssignmentFieldDefinition,
    Employee,
    EmployeeAssignment,
    EmployeeOverride,
)
from app.services.assignment_resolution import (
    resolve_employees_assignments_for_date,
)
from app.services.audit import record_audit_log, snapshot_assignment
from app.services.automated_access import reconcile_automated_roles
from app.services.overrides import FinalAssignment, apply_employee_overrides
from app.services.policy_engine import resolve_employee_assignments
from app.services.policy_matching import replace_employee_policies


class AssignmentReconciliationOrderError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        employee_id: int,
        requested_at: datetime,
        latest_assignment_start: datetime,
    ) -> None:
        super().__init__(message)
        self.metadata = {
            "employee_id": employee_id,
            "requested_at": requested_at,
            "latest_assignment_start": latest_assignment_start,
        }


def reconcile_employees(
    session: Session,
    employee_ids: Collection[int],
    reconciliation_at: datetime | None = None,
    *,
    actor: str = "system",
) -> dict[int, list[EmployeeAssignment]]:
    """Reconcile a deduplicated employee batch at one consistent instant."""
    ids = sorted(set(employee_ids))
    if not ids:
        return {}
    session.flush()
    effective_at = ensure_utc(reconciliation_at or current_datetime())
    evaluation_date = effective_at.date()
    employees = {
        employee.id: employee
        for employee in session.scalars(
            select(Employee).where(Employee.id.in_(ids)).order_by(Employee.id)
        )
    }
    resolutions = resolve_employees_assignments_for_date(
        session,
        ids,
        evaluation_date,
    )
    reconciled: dict[int, list[EmployeeAssignment]] = {}
    for employee_id in ids:
        employee = employees.get(employee_id)
        if employee is None:
            continue
        resolution = resolutions[employee.id]
        replace_employee_policies(
            session,
            employee.id,
            resolution.policy_ids,
        )
        reconcile_automated_roles(
            session,
            employee_id=employee.id,
            policy_ids=resolution.policy_ids,
            evaluation_date=evaluation_date,
            timestamp=effective_at,
            actor=actor,
        )
        reconciled[employee.id] = refresh_employee_assignments(
            session,
            employee,
            evaluation_date,
            effective_at,
            actor,
            desired_assignments=resolution.assignments,
        )
    return reconciled


def refresh_employee_assignments(
    session: Session,
    employee: Employee,
    evaluation_date: date | None = None,
    reconciliation_at: datetime | None = None,
    actor: str = "system",
    *,
    desired_assignments: Collection[FinalAssignment] | None = None,
) -> list[EmployeeAssignment]:
    effective_at = _reconciliation_timestamp(evaluation_date, reconciliation_at)
    policy_evaluation_date = evaluation_date or effective_at.date()
    _reject_out_of_order_reconciliation(session, employee.id, effective_at)
    if desired_assignments is None:
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
    else:
        final_assignments = list(desired_assignments)
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
                        *[
                            item.assignment_field_definition_id
                            for item in current_assignments
                        ],
                        *[
                            item.assignment_field_definition_id
                            for item in final_assignments
                        ],
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
            explanation=item.explanation or {},
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
            "Assignment reconciliation cannot run before existing assignment history",
            employee_id=employee_id,
            requested_at=reconciliation_at,
            latest_assignment_start=ensure_utc(latest_start),
        )


def _assignment_key(
    assignment: EmployeeAssignment | FinalAssignment,
) -> tuple[int, str, int | None, int | None, str]:
    return (
        assignment.assignment_field_definition_id,
        assignment.value,
        assignment.source_policy_version_id,
        assignment.source_override_id,
        json.dumps(
            _stable_explanation(assignment.explanation or {}),
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _stable_explanation(value: Any) -> Any:
    """Remove clock-only evidence that should not create assignment churn."""
    if isinstance(value, dict):
        return {
            key: _stable_explanation(item)
            for key, item in value.items()
            if key != "evaluation_date"
        }
    if isinstance(value, list):
        return [_stable_explanation(item) for item in value]
    return value
