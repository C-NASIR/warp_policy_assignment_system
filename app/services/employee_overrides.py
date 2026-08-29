from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Employee, EmployeeOverride, FieldDefinition
from app.services.reconciliation import refresh_employee_assignments


class EmployeeOverrideResourceNotFoundError(ValueError):
    pass


class EmployeeOverrideConflictError(ValueError):
    pass


def list_employee_overrides(session: Session, employee_id: int) -> list[EmployeeOverride]:
    _get_employee(session, employee_id)
    return list(
        session.scalars(
            select(EmployeeOverride)
            .where(EmployeeOverride.employee_id == employee_id)
            .options(joinedload(EmployeeOverride.field_definition))
            .order_by(
                EmployeeOverride.field_definition_id,
                EmployeeOverride.value,
                EmployeeOverride.id,
            )
        )
    )


def create_employee_override(
    session: Session,
    employee_id: int,
    field_definition_id: int,
    value: str,
) -> EmployeeOverride:
    employee = _get_employee(session, employee_id)
    field_definition = _get_field_definition(session, field_definition_id)
    _validate_override_cardinality(
        session,
        employee_id,
        field_definition,
        value,
    )

    override = EmployeeOverride(
        employee=employee,
        field_definition=field_definition,
        value=value,
    )
    session.add(override)
    session.flush()
    refresh_employee_assignments(session, employee)
    return override


def update_employee_override(
    session: Session,
    employee_id: int,
    override_id: int,
    field_definition_id: int | None,
    value: str | None,
) -> EmployeeOverride:
    employee = _get_employee(session, employee_id)
    override = _get_override(session, employee_id, override_id)
    target_field = (
        _get_field_definition(session, field_definition_id)
        if field_definition_id is not None
        else override.field_definition
    )
    target_value = value if value is not None else override.value
    _validate_override_cardinality(
        session,
        employee_id,
        target_field,
        target_value,
        excluded_override_id=override.id,
    )

    override.field_definition = target_field
    override.value = target_value
    session.flush()
    refresh_employee_assignments(session, employee)
    return override


def delete_employee_override(
    session: Session,
    employee_id: int,
    override_id: int,
) -> None:
    employee = _get_employee(session, employee_id)
    override = _get_override(session, employee_id, override_id)
    session.delete(override)
    session.flush()
    refresh_employee_assignments(session, employee)


def _validate_override_cardinality(
    session: Session,
    employee_id: int,
    field_definition: FieldDefinition,
    value: str,
    excluded_override_id: int | None = None,
) -> None:
    statement = select(EmployeeOverride).where(
        EmployeeOverride.employee_id == employee_id,
        EmployeeOverride.field_definition_id == field_definition.id,
    )
    if excluded_override_id is not None:
        statement = statement.where(EmployeeOverride.id != excluded_override_id)
    existing = list(session.scalars(statement))

    if field_definition.cardinality == "one" and existing:
        raise EmployeeOverrideConflictError(
            f"Field '{field_definition.name}' accepts only one override value per employee"
        )
    if any(item.value == value for item in existing):
        raise EmployeeOverrideConflictError(
            f"Override value '{value}' already exists for field '{field_definition.name}'"
        )


def _get_employee(session: Session, employee_id: int) -> Employee:
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise EmployeeOverrideResourceNotFoundError(f"Employee {employee_id} not found")
    return employee


def _get_field_definition(session: Session, field_definition_id: int) -> FieldDefinition:
    field_definition = session.get(FieldDefinition, field_definition_id)
    if field_definition is None:
        raise EmployeeOverrideResourceNotFoundError(
            f"Field definition {field_definition_id} not found"
        )
    return field_definition


def _get_override(session: Session, employee_id: int, override_id: int) -> EmployeeOverride:
    override = session.scalar(
        select(EmployeeOverride)
        .where(
            EmployeeOverride.id == override_id,
            EmployeeOverride.employee_id == employee_id,
        )
        .options(joinedload(EmployeeOverride.field_definition))
    )
    if override is None:
        raise EmployeeOverrideResourceNotFoundError(
            f"Override {override_id} not found for employee {employee_id}"
        )
    return override
