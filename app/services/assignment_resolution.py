from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, EmployeeOverride
from app.services.overrides import FinalAssignment, apply_employee_overrides
from app.services.policy_engine import resolve_policy_assignments
from app.services.policy_matching import find_matching_policy_ids


@dataclass(frozen=True)
class EmployeeAssignmentResolution:
    employee_id: int
    evaluation_date: date
    policy_ids: tuple[int, ...]
    assignments: tuple[FinalAssignment, ...]


def resolve_employee_assignments_for_date(
    session: Session,
    employee: Employee,
    evaluation_date: date,
) -> EmployeeAssignmentResolution:
    """Calculate one employee's desired assignments without persisting projections."""
    policy_ids = tuple(
        find_matching_policy_ids(session, employee.id, evaluation_date)
    )
    policy_assignments = resolve_policy_assignments(
        session,
        policy_ids,
        evaluation_date,
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
    assignments = tuple(apply_employee_overrides(policy_assignments, overrides))
    return EmployeeAssignmentResolution(
        employee_id=employee.id,
        evaluation_date=evaluation_date,
        policy_ids=policy_ids,
        assignments=assignments,
    )


def resolve_employees_assignments_for_date(
    session: Session,
    employee_ids: list[int] | tuple[int, ...] | set[int],
    evaluation_date: date,
) -> dict[int, EmployeeAssignmentResolution]:
    """Calculate a deduplicated employee batch without changing database state."""
    ids = sorted(set(employee_ids))
    if not ids:
        return {}
    employees = list(
        session.scalars(
            select(Employee).where(Employee.id.in_(ids)).order_by(Employee.id)
        )
    )
    return {
        employee.id: resolve_employee_assignments_for_date(
            session,
            employee,
            evaluation_date,
        )
        for employee in employees
    }
