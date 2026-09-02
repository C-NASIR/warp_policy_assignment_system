from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import Select

from app.dates import current_datetime, ensure_utc
from app.models import EmployeeAssignment


def get_employee_assignments_as_of(
    session: Session,
    employee_id: int,
    as_of: datetime | None = None,
) -> list[EmployeeAssignment]:
    """Return assignments effective at one instant using [from, until) ranges."""
    return list(session.scalars(employee_assignments_as_of_statement(employee_id, as_of)))


def employee_assignments_as_of_statement(
    employee_id: int,
    as_of: datetime | None = None,
) -> Select[tuple[EmployeeAssignment]]:
    effective_at = ensure_utc(as_of or current_datetime())
    return (
        select(EmployeeAssignment)
        .where(
            EmployeeAssignment.employee_id == employee_id,
            EmployeeAssignment.effective_from <= effective_at,
            or_(
                EmployeeAssignment.effective_until.is_(None),
                EmployeeAssignment.effective_until > effective_at,
            ),
        )
        .options(joinedload(EmployeeAssignment.assignment_field_definition))
        .order_by(
            EmployeeAssignment.assignment_field_definition_id,
            EmployeeAssignment.value,
            EmployeeAssignment.id,
        )
    )


def get_current_employee_assignments(
    session: Session,
    employee_id: int,
) -> list[EmployeeAssignment]:
    return get_employee_assignments_as_of(session, employee_id)


def get_employee_assignment_history(
    session: Session,
    employee_id: int,
) -> list[EmployeeAssignment]:
    return list(session.scalars(employee_assignment_history_statement(employee_id)))


def employee_assignment_history_statement(
    employee_id: int,
) -> Select[tuple[EmployeeAssignment]]:
    return (
        select(EmployeeAssignment)
        .where(EmployeeAssignment.employee_id == employee_id)
        .options(joinedload(EmployeeAssignment.assignment_field_definition))
        .order_by(
            EmployeeAssignment.assignment_field_definition_id,
            EmployeeAssignment.effective_from,
            EmployeeAssignment.id,
        )
    )
