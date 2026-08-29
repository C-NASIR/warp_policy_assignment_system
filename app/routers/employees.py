from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dependencies import DatabaseSession
from app.models import Employee, EmployeeAssignment
from app.schemas import (
    AssignmentRead,
    EmployeeCreate,
    EmployeeRead,
    EmployeeUpdate,
)
from app.services.employees import create_employee, update_employee
from app.services.policy_matching import refresh_employee_policies
from app.services.reconciliation import reconcile_employee

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
def assignments(employee_id: int, session: DatabaseSession) -> list[EmployeeAssignment]:
    _employee_or_404(session, employee_id)
    return list(
        session.scalars(
            select(EmployeeAssignment)
            .where(EmployeeAssignment.employee_id == employee_id)
            .options(joinedload(EmployeeAssignment.field_definition))
            .order_by(EmployeeAssignment.field_definition_id, EmployeeAssignment.value)
        )
    )


@router.post("/{employee_id}/reconcile", response_model=list[AssignmentRead])
def reconcile(employee_id: int, session: DatabaseSession) -> list[EmployeeAssignment]:
    employee = _employee_or_404(session, employee_id)
    refresh_employee_policies(session, employee.id)
    reconcile_employee(session, employee)
    return assignments(employee_id, session)
