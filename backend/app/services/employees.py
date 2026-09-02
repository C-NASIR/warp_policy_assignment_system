from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dates import current_datetime
from app.models import Employee
from app.schemas import EmployeeCreate, EmployeeUpdate
from app.services.audit import record_audit_log, snapshot_entity
from app.services.condition_impacts import (
    EmployeeMutation,
    find_impacted_employee_ids,
)
from app.services.org_chart import get_descendant_ids, validate_manager_assignment
from app.services.reconciliation import reconcile_employees
from app.services.scheduled_reconciliations import (
    EMPLOYEE_ENTITY,
    cancel_pending_reconciliations,
)
from app.services.tenure_scheduling import sync_employee_tenure_schedules


def create_employee(
    session: Session,
    data: EmployeeCreate,
    actor: str = "system",
) -> Employee:
    validate_manager_assignment(
        session,
        employee_id=None,
        manager_id=data.manager_id,
    )
    employee = Employee(**data.model_dump())
    session.add(employee)
    session.flush()
    reconciliation_at = current_datetime()
    after = snapshot_entity(employee)
    record_audit_log(
        session,
        actor=actor,
        entity_type="Employee",
        entity_id=employee.id,
        action="created",
        before=None,
        after=after,
        timestamp=reconciliation_at,
    )
    impacted_ids = find_impacted_employee_ids(
        session,
        EmployeeMutation(
            employee_id=employee.id,
            changed_columns=frozenset(data.model_dump()),
            before={},
            after=after,
        ),
    )
    reconcile_employees(session, impacted_ids, reconciliation_at)
    sync_employee_tenure_schedules(session, employee, as_of=reconciliation_at)
    return employee


def update_employee(
    session: Session,
    employee: Employee,
    data: EmployeeUpdate,
    actor: str = "system",
) -> Employee:
    before = snapshot_entity(employee)
    if "manager_id" in data.model_fields_set:
        validate_manager_assignment(
            session,
            employee_id=employee.id,
            manager_id=data.manager_id,
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    session.flush()
    after = snapshot_entity(employee)
    changed_columns = frozenset(
        field
        for field in data.model_fields_set
        if before.get(field) != after.get(field)
    )
    if not changed_columns:
        return employee
    reconciliation_at = current_datetime()
    record_audit_log(
        session,
        actor=actor,
        entity_type="Employee",
        entity_id=employee.id,
        action="manager_changed" if "manager_id" in changed_columns else "changed",
        before=before,
        after=after,
        timestamp=reconciliation_at,
    )
    impacted_ids = find_impacted_employee_ids(
        session,
        EmployeeMutation(
            employee_id=employee.id,
            changed_columns=changed_columns,
            before=before,
            after=after,
        ),
    )
    reconcile_employees(session, impacted_ids, reconciliation_at)
    if "start_date" in changed_columns:
        sync_employee_tenure_schedules(session, employee, as_of=reconciliation_at)
    return employee


def delete_employee(
    session: Session,
    employee: Employee,
    actor: str = "system",
) -> None:
    reconciliation_at = current_datetime()
    before = snapshot_entity(employee)
    descendant_ids = get_descendant_ids(session, employee.id)
    direct_reports = list(
        session.scalars(select(Employee).where(Employee.manager_id == employee.id))
    )
    for report in direct_reports:
        report.manager_id = None
    impacted_ids = set(descendant_ids)
    if employee.manager_id is not None:
        impacted_ids.add(employee.manager_id)
    cancel_pending_reconciliations(
        session,
        entity_type=EMPLOYEE_ENTITY,
        entity_ids=[employee.id],
    )
    session.delete(employee)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="Employee",
        entity_id=employee.id,
        action="deleted",
        before=before,
        after=None,
        timestamp=reconciliation_at,
    )
    reconcile_employees(session, impacted_ids, reconciliation_at)
