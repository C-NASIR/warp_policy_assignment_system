from datetime import datetime

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dates import current_datetime
from app.dependencies import DatabaseSession
from app.models import Employee, EmployeeAssignment, EmployeeOverride
from app.schemas import (
    AssignmentRead,
    EmployeeCreate,
    EmployeeOverrideCreate,
    EmployeeOverrideRead,
    EmployeeOverrideUpdate,
    EmployeeRead,
    EmployeeUpdate,
)
from app.services.employee_assignments import (
    get_current_employee_assignments,
    get_employee_assignment_history,
    get_employee_assignments_as_of,
)
from app.services.employee_overrides import (
    create_employee_override,
    delete_employee_override,
    list_employee_overrides,
    update_employee_override,
)
from app.services.employees import create_employee, update_employee
from app.services.policy_matching import refresh_employee_policies
from app.services.reconciliation import refresh_employee_assignments

router = APIRouter(prefix="/employees", tags=["employees"])


def _employee_or_404(session: Session, employee_id: int) -> Employee:
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    return employee


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create(data: EmployeeCreate, session: DatabaseSession) -> Employee:
    return create_employee(session, data)


@router.get("", response_model=list[EmployeeRead])
def list_all(session: DatabaseSession) -> list[Employee]:
    return list(session.scalars(select(Employee).order_by(Employee.id)))


@router.get("/{employee_id}", response_model=EmployeeRead)
def get(employee_id: int, session: DatabaseSession) -> Employee:
    return _employee_or_404(session, employee_id)


@router.patch("/{employee_id}", response_model=EmployeeRead)
def patch(employee_id: int, data: EmployeeUpdate, session: DatabaseSession) -> Employee:
    return update_employee(session, _employee_or_404(session, employee_id), data)


@router.get("/{employee_id}/assignments", response_model=list[AssignmentRead])
def assignments(
    employee_id: int,
    session: DatabaseSession,
    as_of: datetime | None = None,
) -> list[EmployeeAssignment]:
    _employee_or_404(session, employee_id)
    if as_of is None:
        return get_current_employee_assignments(session, employee_id)
    return get_employee_assignments_as_of(session, employee_id, as_of)


@router.get(
    "/{employee_id}/assignments/history",
    response_model=list[AssignmentRead],
)
def assignment_history(
    employee_id: int,
    session: DatabaseSession,
) -> list[EmployeeAssignment]:
    _employee_or_404(session, employee_id)
    return get_employee_assignment_history(session, employee_id)


@router.get("/{employee_id}/overrides", response_model=list[EmployeeOverrideRead])
def overrides(employee_id: int, session: DatabaseSession) -> list[EmployeeOverride]:
    return list_employee_overrides(session, employee_id)


@router.post(
    "/{employee_id}/overrides",
    response_model=EmployeeOverrideRead,
    status_code=status.HTTP_201_CREATED,
)
def create_override(
    employee_id: int,
    data: EmployeeOverrideCreate,
    session: DatabaseSession,
) -> EmployeeOverride:
    return create_employee_override(
        session,
        employee_id,
        data.field_definition_id,
        data.value,
    )


@router.patch(
    "/{employee_id}/overrides/{override_id}",
    response_model=EmployeeOverrideRead,
)
def patch_override(
    employee_id: int,
    override_id: int,
    data: EmployeeOverrideUpdate,
    session: DatabaseSession,
) -> EmployeeOverride:
    return update_employee_override(
        session,
        employee_id,
        override_id,
        data.field_definition_id,
        data.value,
    )


@router.delete(
    "/{employee_id}/overrides/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_override(
    employee_id: int,
    override_id: int,
    session: DatabaseSession,
) -> Response:
    delete_employee_override(session, employee_id, override_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{employee_id}/refresh", response_model=list[AssignmentRead])
def refresh(employee_id: int, session: DatabaseSession) -> list[EmployeeAssignment]:
    employee = _employee_or_404(session, employee_id)
    reconciliation_at = current_datetime()
    evaluation_date = reconciliation_at.date()
    refresh_employee_policies(session, employee.id, evaluation_date)
    refresh_employee_assignments(
        session,
        employee,
        evaluation_date,
        reconciliation_at,
    )
    return assignments(employee_id, session)
