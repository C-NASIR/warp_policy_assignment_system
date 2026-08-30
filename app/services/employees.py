from sqlalchemy.orm import Session

from app.dates import current_datetime
from app.models import Employee
from app.schemas import EmployeeCreate, EmployeeUpdate
from app.services.policy_matching import refresh_employee_policies
from app.services.reconciliation import refresh_employee_assignments


def create_employee(session: Session, data: EmployeeCreate) -> Employee:
    employee = Employee(**data.model_dump())
    session.add(employee)
    session.flush()
    reconciliation_at = current_datetime()
    evaluation_date = reconciliation_at.date()
    refresh_employee_policies(session, employee.id, evaluation_date)
    refresh_employee_assignments(
        session,
        employee,
        evaluation_date,
        reconciliation_at,
    )
    return employee


def update_employee(session: Session, employee: Employee, data: EmployeeUpdate) -> Employee:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    session.flush()
    reconciliation_at = current_datetime()
    evaluation_date = reconciliation_at.date()
    refresh_employee_policies(session, employee.id, evaluation_date)
    refresh_employee_assignments(
        session,
        employee,
        evaluation_date,
        reconciliation_at,
    )
    return employee
