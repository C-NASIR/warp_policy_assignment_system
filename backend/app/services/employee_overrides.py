from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import Select

from app.dates import current_datetime
from app.models import AssignmentFieldDefinition, Employee, EmployeeOverride
from app.services.audit import record_audit_log, snapshot_override
from app.services.reconciliation import reconcile_employees


class EmployeeOverrideResourceNotFoundError(ValueError):
    pass


class EmployeeOverrideConflictError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        employee_id: int | None = None,
        assignment_field_definition_id: int | None = None,
        assignment_field_name: str | None = None,
        value: str | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = {
            "employee_id": employee_id,
            "assignment_field_definition_id": assignment_field_definition_id,
            "assignment_field_name": assignment_field_name,
            "value": value,
        }


def list_employee_overrides(session: Session, employee_id: int) -> list[EmployeeOverride]:
    _get_employee(session, employee_id)
    return list(session.scalars(employee_overrides_statement(employee_id)))


def employee_overrides_statement(
    employee_id: int,
) -> Select[tuple[EmployeeOverride]]:
    return (
        select(EmployeeOverride)
        .where(
            EmployeeOverride.employee_id == employee_id,
            EmployeeOverride.retired_at.is_(None),
        )
        .options(joinedload(EmployeeOverride.assignment_field_definition))
        .order_by(
            EmployeeOverride.assignment_field_definition_id,
            EmployeeOverride.value,
            EmployeeOverride.id,
        )
    )


def create_employee_override(
    session: Session,
    employee_id: int,
    assignment_field_definition_id: int,
    value: str,
    actor: str = "system",
) -> EmployeeOverride:
    employee = _get_employee(session, employee_id)
    assignment_field_definition = _get_assignment_field_definition(
        session,
        assignment_field_definition_id,
    )
    _validate_override_cardinality(
        session,
        employee_id,
        assignment_field_definition,
        value,
    )

    override = EmployeeOverride(
        employee=employee,
        assignment_field_definition=assignment_field_definition,
        value=value,
    )
    reconciliation_at = current_datetime()
    session.add(override)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="EmployeeOverride",
        entity_id=override.id,
        action="created",
        before=None,
        after=snapshot_override(override),
        timestamp=reconciliation_at,
    )
    reconcile_employees(session, [employee.id], reconciliation_at)
    return override


def update_employee_override(
    session: Session,
    employee_id: int,
    override_id: int,
    assignment_field_definition_id: int | None,
    value: str | None,
    actor: str = "system",
) -> EmployeeOverride:
    employee = _get_employee(session, employee_id)
    override = _get_override(session, employee_id, override_id)
    target_field = (
        _get_assignment_field_definition(session, assignment_field_definition_id)
        if assignment_field_definition_id is not None
        else override.assignment_field_definition
    )
    target_value = value if value is not None else override.value
    if (
        target_field.id == override.assignment_field_definition_id
        and target_value == override.value
    ):
        return override
    _validate_override_cardinality(
        session,
        employee_id,
        target_field,
        target_value,
        excluded_override_id=override.id,
    )

    reconciliation_at = current_datetime()
    before = snapshot_override(override)
    override.retired_at = reconciliation_at
    replacement = EmployeeOverride(
        employee=employee,
        assignment_field_definition=target_field,
        value=target_value,
    )
    session.add(replacement)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="EmployeeOverride",
        entity_id=replacement.id,
        action="changed",
        before=before,
        after=snapshot_override(replacement),
        timestamp=reconciliation_at,
    )
    reconcile_employees(session, [employee.id], reconciliation_at)
    return replacement


def delete_employee_override(
    session: Session,
    employee_id: int,
    override_id: int,
    actor: str = "system",
) -> None:
    employee = _get_employee(session, employee_id)
    override = _get_override(session, employee_id, override_id)
    reconciliation_at = current_datetime()
    before = snapshot_override(override)
    override.retired_at = reconciliation_at
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="EmployeeOverride",
        entity_id=override.id,
        action="removed",
        before=before,
        after=None,
        timestamp=reconciliation_at,
    )
    reconcile_employees(session, [employee.id], reconciliation_at)


def _validate_override_cardinality(
    session: Session,
    employee_id: int,
    assignment_field_definition: AssignmentFieldDefinition,
    value: str,
    excluded_override_id: int | None = None,
) -> None:
    statement = select(EmployeeOverride).where(
        EmployeeOverride.employee_id == employee_id,
        EmployeeOverride.assignment_field_definition_id == assignment_field_definition.id,
        EmployeeOverride.retired_at.is_(None),
    )
    if excluded_override_id is not None:
        statement = statement.where(EmployeeOverride.id != excluded_override_id)
    existing = list(session.scalars(statement))

    if assignment_field_definition.cardinality == "one" and existing:
        raise EmployeeOverrideConflictError(
            f"Field '{assignment_field_definition.name}' accepts only one "
            "override value per employee",
            employee_id=employee_id,
            assignment_field_definition_id=assignment_field_definition.id,
            assignment_field_name=assignment_field_definition.name,
            value=value,
        )
    if any(item.value == value for item in existing):
        raise EmployeeOverrideConflictError(
            f"Override value '{value}' already exists for field "
            f"'{assignment_field_definition.name}'",
            employee_id=employee_id,
            assignment_field_definition_id=assignment_field_definition.id,
            assignment_field_name=assignment_field_definition.name,
            value=value,
        )


def _get_employee(session: Session, employee_id: int) -> Employee:
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise EmployeeOverrideResourceNotFoundError(f"Employee {employee_id} not found")
    return employee


def _get_assignment_field_definition(
    session: Session,
    assignment_field_definition_id: int,
) -> AssignmentFieldDefinition:
    assignment_field_definition = session.get(
        AssignmentFieldDefinition,
        assignment_field_definition_id,
    )
    if assignment_field_definition is None:
        raise EmployeeOverrideResourceNotFoundError(
            "Assignment field definition "
            f"{assignment_field_definition_id} not found"
        )
    return assignment_field_definition


def _get_override(session: Session, employee_id: int, override_id: int) -> EmployeeOverride:
    override = session.scalar(
        select(EmployeeOverride)
        .where(
            EmployeeOverride.id == override_id,
            EmployeeOverride.employee_id == employee_id,
            EmployeeOverride.retired_at.is_(None),
        )
        .options(joinedload(EmployeeOverride.assignment_field_definition))
    )
    if override is None:
        raise EmployeeOverrideResourceNotFoundError(
            f"Override {override_id} not found for employee {employee_id}"
        )
    return override
