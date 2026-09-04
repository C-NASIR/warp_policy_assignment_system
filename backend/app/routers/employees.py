from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import or_, select

from app.dates import current_date, current_datetime
from app.dependencies import (
    AssignmentFieldScope,
    AuditActor,
    DatabaseSession,
    EmployeeScope,
)
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
from app.services.assignment_field_visibility import (
    AssignmentFieldVisibility,
    visible_assignment_field_or_404,
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
from app.services.employee_visibility import (
    require_employee_creation_scope,
    visible_employee_or_404,
)
from app.services.employees import create_employee, delete_employee, update_employee
from app.services.impact_summaries import build_assignment_summary
from app.services.reconciliation import reconcile_employees

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create(
    data: EmployeeCreate,
    session: DatabaseSession,
    actor: AuditActor,
    visibility: EmployeeScope,
) -> Employee:
    require_employee_creation_scope(session, visibility, data.manager_id)
    return create_employee(session, data, actor)


@router.get("", response_model=list[EmployeeRead])
def list_all(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    visibility: EmployeeScope,
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
    statement = visibility.apply(select(Employee))
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
def get(
    employee_id: int,
    session: DatabaseSession,
    visibility: EmployeeScope,
) -> Employee:
    return visible_employee_or_404(session, visibility, employee_id)


@router.get(
    "/{employee_id}/assignment-summary",
    response_model=AssignmentSummaryRead,
)
def assignment_summary(
    employee_id: int,
    session: DatabaseSession,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    evaluation_date: date | None = None,
) -> AssignmentSummaryRead:
    visible_employee_or_404(session, visibility, employee_id)
    return build_assignment_summary(
        session,
        evaluation_date or current_date(),
        employee_id=employee_id,
        visible_assignment_field_ids=(
            None
            if field_visibility.unrestricted
            else set(field_visibility.assignment_field_ids)
        ),
    )


@router.patch("/{employee_id}", response_model=EmployeeRead)
def patch(
    employee_id: int,
    data: EmployeeUpdate,
    session: DatabaseSession,
    actor: AuditActor,
    visibility: EmployeeScope,
) -> Employee:
    employee = visible_employee_or_404(session, visibility, employee_id)
    if (
        "manager_id" in data.model_fields_set
        and data.manager_id is not None
        and data.manager_id != employee.manager_id
    ):
        visible_employee_or_404(session, visibility, data.manager_id)
    return update_employee(
        session,
        employee,
        data,
        actor,
    )


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    employee_id: int,
    session: DatabaseSession,
    actor: AuditActor,
    visibility: EmployeeScope,
) -> Response:
    delete_employee(
        session,
        visible_employee_or_404(session, visibility, employee_id),
        actor,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{employee_id}/assignments", response_model=list[AssignmentRead])
def assignments(
    employee_id: int,
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    as_of: datetime | None = None,
    assignment_field_definition_id: Annotated[int | None, Query(gt=0)] = None,
    value: Annotated[str | None, Query(max_length=500)] = None,
    source: Literal["policy", "override"] | None = None,
) -> list[EmployeeAssignment]:
    visible_employee_or_404(session, visibility, employee_id)
    statement = employee_assignments_as_of_statement(employee_id, as_of)
    statement = field_visibility.apply(
        statement,
        EmployeeAssignment.assignment_field_definition_id,
    )
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
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    assignment_field_definition_id: Annotated[int | None, Query(gt=0)] = None,
    value: Annotated[str | None, Query(max_length=500)] = None,
    source: Literal["policy", "override"] | None = None,
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
) -> list[EmployeeAssignment]:
    visible_employee_or_404(session, visibility, employee_id)
    statement = employee_assignment_history_statement(employee_id)
    statement = field_visibility.apply(
        statement,
        EmployeeAssignment.assignment_field_definition_id,
    )
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
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    assignment_field_definition_id: Annotated[int | None, Query(gt=0)] = None,
    value: Annotated[str | None, Query(max_length=500)] = None,
) -> list[EmployeeOverride]:
    visible_employee_or_404(session, visibility, employee_id)
    statement = employee_overrides_statement(employee_id)
    statement = field_visibility.apply(
        statement,
        EmployeeOverride.assignment_field_definition_id,
    )
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
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
) -> EmployeeOverride:
    visible_employee_or_404(session, visibility, employee_id)
    visible_assignment_field_or_404(
        session,
        field_visibility,
        data.assignment_field_definition_id,
    )
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
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
) -> EmployeeOverride:
    visible_employee_or_404(session, visibility, employee_id)
    _visible_override_or_404(
        session,
        field_visibility,
        employee_id,
        override_id,
    )
    if data.assignment_field_definition_id is not None:
        visible_assignment_field_or_404(
            session,
            field_visibility,
            data.assignment_field_definition_id,
        )
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
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
) -> Response:
    visible_employee_or_404(session, visibility, employee_id)
    _visible_override_or_404(
        session,
        field_visibility,
        employee_id,
        override_id,
    )
    delete_employee_override(session, employee_id, override_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{employee_id}/refresh", response_model=list[AssignmentRead])
def refresh(
    employee_id: int,
    session: DatabaseSession,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
) -> list[EmployeeAssignment]:
    visible_employee_or_404(session, visibility, employee_id)
    reconciliation_at = current_datetime()
    reconciled = reconcile_employees(
        session,
        [employee_id],
        reconciliation_at,
    )
    return [
        assignment
        for assignment in reconciled[employee_id]
        if field_visibility.can_access(
            assignment.assignment_field_definition_id
        )
    ]


def _visible_override_or_404(
    session: DatabaseSession,
    visibility: AssignmentFieldVisibility,
    employee_id: int,
    override_id: int,
) -> EmployeeOverride:
    override = session.scalar(
        visibility.apply(
            select(EmployeeOverride).where(
                EmployeeOverride.id == override_id,
                EmployeeOverride.employee_id == employee_id,
                EmployeeOverride.retired_at.is_(None),
            ),
            EmployeeOverride.assignment_field_definition_id,
        )
    )
    if override is None:
        raise HTTPException(
            status_code=404,
            detail=f"Override {override_id} not found for employee {employee_id}",
        )
    return override
