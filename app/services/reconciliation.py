from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Employee, EmployeeAssignment
from app.services.policy_engine import resolve_assignments


def reconcile_employee(session: Session, employee: Employee) -> list[EmployeeAssignment]:
    desired = resolve_assignments(session, employee)
    session.execute(delete(EmployeeAssignment).where(EmployeeAssignment.employee_id == employee.id))
    session.flush()
    assignments = [
        EmployeeAssignment(
            employee_id=employee.id,
            field_definition_id=item.field_definition_id,
            value=item.value,
            source_policy_id=item.source_policy_id,
        )
        for item in desired
    ]
    session.add_all(assignments)
    session.flush()
    return assignments
