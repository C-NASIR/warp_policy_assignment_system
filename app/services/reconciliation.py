from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Employee, EmployeeAssignment, EmployeeOverride
from app.services.overrides import apply_employee_overrides
from app.services.policy_engine import resolve_employee_assignments


def refresh_employee_assignments(session: Session, employee: Employee) -> list[EmployeeAssignment]:
    resolved_assignments = resolve_employee_assignments(session, employee)
    overrides = list(
        session.scalars(
            select(EmployeeOverride)
            .where(EmployeeOverride.employee_id == employee.id)
            .order_by(
                EmployeeOverride.field_definition_id,
                EmployeeOverride.value,
                EmployeeOverride.id,
            )
        )
    )
    final_assignments = apply_employee_overrides(resolved_assignments, overrides)
    session.execute(delete(EmployeeAssignment).where(EmployeeAssignment.employee_id == employee.id))
    session.flush()
    assignments = [
        EmployeeAssignment(
            employee_id=employee.id,
            field_definition_id=item.field_definition_id,
            value=item.value,
            source_policy_id=item.source_policy_id,
            source_override_id=item.source_override_id,
        )
        for item in final_assignments
    ]
    session.add_all(assignments)
    session.flush()
    session.expire(employee, ["assignments"])
    return assignments
