from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dates import current_date, start_of_day
from app.models import AssignmentFieldDefinition, Employee, EmployeeAssignment
from app.services.assignment_resolution import (
    resolve_employees_assignments_for_date,
)
from app.services.employee_assignments import (
    get_current_employee_assignments,
    get_employee_assignments_as_of,
)

AssignmentQueryMode = Literal[
    "recorded_history",
    "current_persisted",
    "calculated_future",
]


class AssignmentQueryEmployeeNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class AssignmentQueryValue:
    assignment_field_definition: AssignmentFieldDefinition
    value: str
    source_policy_version_id: int | None
    source_override_id: int | None
    explanation: dict[str, Any]
    persisted_assignment_id: int | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None


@dataclass(frozen=True)
class EmployeeAssignmentQueryResult:
    employee_id: int
    evaluation_date: date
    mode: AssignmentQueryMode
    assignments: tuple[AssignmentQueryValue, ...]


def query_employee_assignments(
    session: Session,
    employee_ids: list[int] | tuple[int, ...] | set[int],
    evaluation_date: date,
    *,
    visible_assignment_field_ids: set[int] | None = None,
) -> list[EmployeeAssignmentQueryResult]:
    """Answer recorded-past, current, and calculated-future assignment questions."""
    ids = sorted(set(employee_ids))
    employees = {
        employee.id: employee
        for employee in session.scalars(
            select(Employee).where(Employee.id.in_(ids)).order_by(Employee.id)
        )
    }
    missing_ids = [employee_id for employee_id in ids if employee_id not in employees]
    if missing_ids:
        rendered = ", ".join(str(employee_id) for employee_id in missing_ids)
        raise AssignmentQueryEmployeeNotFoundError(
            f"Employees not found: {rendered}"
        )

    today = current_date()
    if evaluation_date < today:
        return [
            EmployeeAssignmentQueryResult(
                employee_id=employee_id,
                evaluation_date=evaluation_date,
                mode="recorded_history",
                assignments=tuple(
                    _persisted_value(assignment)
                    for assignment in get_employee_assignments_as_of(
                        session,
                        employee_id,
                        start_of_day(evaluation_date),
                    )
                    if visible_assignment_field_ids is None
                    or assignment.assignment_field_definition_id
                    in visible_assignment_field_ids
                ),
            )
            for employee_id in ids
        ]

    if evaluation_date == today:
        return [
            EmployeeAssignmentQueryResult(
                employee_id=employee_id,
                evaluation_date=evaluation_date,
                mode="current_persisted",
                assignments=tuple(
                    _persisted_value(assignment)
                    for assignment in get_current_employee_assignments(
                        session,
                        employee_id,
                    )
                    if visible_assignment_field_ids is None
                    or assignment.assignment_field_definition_id
                    in visible_assignment_field_ids
                ),
            )
            for employee_id in ids
        ]

    resolutions = resolve_employees_assignments_for_date(
        session,
        ids,
        evaluation_date,
    )
    field_ids = {
        assignment.assignment_field_definition_id
        for resolution in resolutions.values()
        for assignment in resolution.assignments
        if visible_assignment_field_ids is None
        or assignment.assignment_field_definition_id
        in visible_assignment_field_ids
    }
    fields = {
        field.id: field
        for field in session.scalars(
            select(AssignmentFieldDefinition).where(
                AssignmentFieldDefinition.id.in_(field_ids)
            )
        )
    }
    return [
        EmployeeAssignmentQueryResult(
            employee_id=employee_id,
            evaluation_date=evaluation_date,
            mode="calculated_future",
            assignments=tuple(
                AssignmentQueryValue(
                    assignment_field_definition=fields[
                        assignment.assignment_field_definition_id
                    ],
                    value=assignment.value,
                    source_policy_version_id=assignment.source_policy_version_id,
                    source_override_id=assignment.source_override_id,
                    explanation=assignment.explanation or {},
                )
                for assignment in resolutions[employee_id].assignments
                if visible_assignment_field_ids is None
                or assignment.assignment_field_definition_id
                in visible_assignment_field_ids
            ),
        )
        for employee_id in ids
    ]


def _persisted_value(assignment: EmployeeAssignment) -> AssignmentQueryValue:
    return AssignmentQueryValue(
        persisted_assignment_id=assignment.id,
        assignment_field_definition=assignment.assignment_field_definition,
        value=assignment.value,
        source_policy_version_id=assignment.source_policy_version_id,
        source_override_id=assignment.source_override_id,
        explanation=assignment.explanation or {},
        effective_from=assignment.effective_from,
        effective_until=assignment.effective_until,
    )
