from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.dates import current_date, current_datetime
from app.dependencies import AuditActor, DatabaseSession
from app.models import Employee, EmployeeAssignment, EmployeeOverride
from app.pagination import Pagination, paginate_scalars
from app.schemas import (
    AssignmentRead,
    AssignmentSummaryRead,
    EmployeeCreate,
    EmployeeOverrideCreate,
    EmployeeOverrideRead,
    EmployeeOverrideUpdate,
    EmployeeRead,
    EmployeeUpdate,
)
from app.services.employee_assignments import (
    employee_assignment_history_statement,
    employee_assignments_as_of_statement,
)
from app.services.employee_overrides import (
    create_employee_override,
    delete_employee_override,
    employee_overrides_statement,
    update_employee_override,
)
from app.services.employees import create_employee, delete_employee, update_employee
from app.services.impact_summaries import build_assignment_summary
from app.services.reconciliation import reconcile_employees

router = APIRouter(prefix="/employees", tags=["employees"])


def _employee_or_404(session: Session, employee_id: int) -> Employee:
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    return employee


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create(data: EmployeeCreate, session: DatabaseSession, actor: AuditActor) -> Employee:
    return create_employee(session, data, actor)


@router.get("", response_model=list[EmployeeRead])
def list_all(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    search: Annotated[str | None, Query(max_length=200)] = None,
    state: Annotated[str | None, Query(max_length=100)] = None,
    department: Annotated[str | None, Query(max_length=100)] = None,
    employee_type: Annotated[str | None, Query(max_length=100)] = None,
    location: Annotated[str | None, Query(max_length=200)] = None,
    manager_id: Annotated[int | None, Query(gt=0)] = None,
    has_manager: bool | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
) -> list[Employee]:
    statement = select(Employee)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Employee.name.ilike(pattern),
                Employee.state.ilike(pattern),
                Employee.department.ilike(pattern),
                Employee.employee_type.ilike(pattern),
                Employee.location.ilike(pattern),
            )
        )
    if state is not None:
        statement = statement.where(Employee.state == state)
    if department is not None:
        statement = statement.where(Employee.department == department)
    if employee_type is not None:
        statement = statement.where(Employee.employee_type == employee_type)
    if location is not None:
        statement = statement.where(Employee.location == location)
    if manager_id is not None:
        statement = statement.where(Employee.manager_id == manager_id)
    if has_manager is not None:
        statement = statement.where(
            Employee.manager_id.is_not(None)
            if has_manager
            else Employee.manager_id.is_(None)
        )
    if start_date_from is not None:
        statement = statement.where(Employee.start_date >= start_date_from)
    if start_date_to is not None:
        statement = statement.where(Employee.start_date <= start_date_to)
    return paginate_scalars(
        session,
        statement.order_by(Employee.id),
        pagination,
        response,
    )


@router.get("/{employee_id}", response_model=EmployeeRead)
def get(employee_id: int, session: DatabaseSession) -> Employee:
    return _employee_or_404(session, employee_id)


@router.get(
    "/{employee_id}/assignment-summary",
    response_model=AssignmentSummaryRead,
)
def assignment_summary(
    employee_id: int,
    session: DatabaseSession,
    evaluation_date: date | None = None,
) -> AssignmentSummaryRead:
    _employee_or_404(session, employee_id)
    return build_assignment_summary(
        session,
        evaluation_date or current_date(),
        employee_id=employee_id,
    )


@router.patch("/{employee_id}", response_model=EmployeeRead)
def patch(
    employee_id: int,
    data: EmployeeUpdate,
    session: DatabaseSession,
    actor: AuditActor,
) -> Employee:
    return update_employee(
        session,
        _employee_or_404(session, employee_id),
        data,
        actor,
    )


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    employee_id: int,
    session: DatabaseSession,
    actor: AuditActor,
) -> Response:
    delete_employee(session, _employee_or_404(session, employee_id), actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{employee_id}/assignments", response_model=list[AssignmentRead])
def assignments(
    employee_id: int,
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    as_of: datetime | None = None,
    assignment_field_definition_id: Annotated[int | None, Query(gt=0)] = None,
    value: Annotated[str | None, Query(max_length=500)] = None,
    source: Literal["policy", "override"] | None = None,
) -> list[EmployeeAssignment]:
    _employee_or_404(session, employee_id)
    statement = employee_assignments_as_of_statement(employee_id, as_of)
    if assignment_field_definition_id is not None:
        statement = statement.where(
            EmployeeAssignment.assignment_field_definition_id
            == assignment_field_definition_id
        )
    if value is not None:
        statement = statement.where(EmployeeAssignment.value == value)
    if source == "policy":
        statement = statement.where(
            EmployeeAssignment.source_policy_version_id.is_not(None)
        )
    elif source == "override":
        statement = statement.where(EmployeeAssignment.source_override_id.is_not(None))
    return paginate_scalars(session, statement, pagination, response)


@router.get(
    "/{employee_id}/assignments/history",
    response_model=list[AssignmentRead],
)
def assignment_history(
    employee_id: int,
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    assignment_field_definition_id: Annotated[int | None, Query(gt=0)] = None,
    value: Annotated[str | None, Query(max_length=500)] = None,
    source: Literal["policy", "override"] | None = None,
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
) -> list[EmployeeAssignment]:
    _employee_or_404(session, employee_id)
    statement = employee_assignment_history_statement(employee_id)
    if assignment_field_definition_id is not None:
        statement = statement.where(
            EmployeeAssignment.assignment_field_definition_id
            == assignment_field_definition_id
        )
    if value is not None:
        statement = statement.where(EmployeeAssignment.value == value)
    if source == "policy":
        statement = statement.where(
            EmployeeAssignment.source_policy_version_id.is_not(None)
        )
    elif source == "override":
        statement = statement.where(EmployeeAssignment.source_override_id.is_not(None))
    if effective_from is not None:
        statement = statement.where(
            EmployeeAssignment.effective_from >= effective_from
        )
    if effective_to is not None:
        statement = statement.where(EmployeeAssignment.effective_from <= effective_to)
    return paginate_scalars(session, statement, pagination, response)


@router.get("/{employee_id}/overrides", response_model=list[EmployeeOverrideRead])
def overrides(
    employee_id: int,
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    assignment_field_definition_id: Annotated[int | None, Query(gt=0)] = None,
    value: Annotated[str | None, Query(max_length=500)] = None,
) -> list[EmployeeOverride]:
    _employee_or_404(session, employee_id)
    statement = employee_overrides_statement(employee_id)
    if assignment_field_definition_id is not None:
        statement = statement.where(
            EmployeeOverride.assignment_field_definition_id
            == assignment_field_definition_id
        )
    if value is not None:
        statement = statement.where(EmployeeOverride.value == value)
    return paginate_scalars(session, statement, pagination, response)


@router.post(
    "/{employee_id}/overrides",
    response_model=EmployeeOverrideRead,
    status_code=status.HTTP_201_CREATED,
)
def create_override(
    employee_id: int,
    data: EmployeeOverrideCreate,
    session: DatabaseSession,
    actor: AuditActor,
) -> EmployeeOverride:
    return create_employee_override(
        session,
        employee_id,
        data.assignment_field_definition_id,
        data.value,
        actor,
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
    actor: AuditActor,
) -> EmployeeOverride:
    return update_employee_override(
        session,
        employee_id,
        override_id,
        data.assignment_field_definition_id,
        data.value,
        actor,
    )


@router.delete(
    "/{employee_id}/overrides/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_override(
    employee_id: int,
    override_id: int,
    session: DatabaseSession,
    actor: AuditActor,
) -> Response:
    delete_employee_override(session, employee_id, override_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{employee_id}/refresh", response_model=list[AssignmentRead])
def refresh(employee_id: int, session: DatabaseSession) -> list[EmployeeAssignment]:
    _employee_or_404(session, employee_id)
    reconciliation_at = current_datetime()
    reconciled = reconcile_employees(
        session,
        [employee_id],
        reconciliation_at,
    )
    return reconciled[employee_id]
