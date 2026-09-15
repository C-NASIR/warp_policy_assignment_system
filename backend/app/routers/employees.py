from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.dates import current_date, current_datetime
from app.dependencies import (
    AssignmentFieldScope,
    AuditActor,
    DatabaseSession,
    EmployeeScope,
)
from app.models import (
    AssignmentFieldDefinition,
    Employee,
    EmployeeAssignment,
    EmployeeOverride,
)
from app.pagination import Pagination, paginate_scalars
from app.schemas import (
    AssignmentExplanationSummaryRead,
    AssignmentFieldOverrideOptionRead,
    AssignmentFieldIdentityRead,
    AssignmentHistoryRead,
    AssignmentRead,
    AssignmentSummaryRead,
    CurrentAssignmentRead,
    EmployeeCreate,
    EmployeeDetailRead,
    EmployeeDirectoryRead,
    EmployeeManagerCandidateRead,
    EmployeeOverrideCreate,
    EmployeeOverrideRead,
    EmployeeOverrideUpdate,
    EmployeeRead,
    EmployeeReferenceDataRead,
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
from app.services.org_chart import get_descendant_ids
from app.services.reconciliation import reconcile_employees
from app.states import STATES, matching_state_codes, normalize_state_code, state_label

router = APIRouter(prefix="/employees", tags=["employees"])


def _search_employee_id(search: str) -> int | None:
    candidate = search.strip().removeprefix("#")
    return int(candidate) if candidate.isdigit() else None


def _assignment_field_summary(
    assignment: EmployeeAssignment,
) -> AssignmentFieldIdentityRead:
    return AssignmentFieldIdentityRead.model_validate(
        assignment.assignment_field_definition
    )


def _display_condition(condition: dict) -> dict:
    field = str(condition.get("field", ""))
    expected = condition.get("expected")
    actual = condition.get("actual")
    return {
        "field": field,
        "operator": str(condition.get("operator", "")),
        "expected": expected,
        "actual": actual,
        "expected_label": (
            state_label(str(expected)) if field == "state" and expected else None
        ),
        "actual_label": (
            state_label(str(actual)) if field == "state" and actual else None
        ),
    }


def _display_explanation(
    assignment: EmployeeAssignment,
) -> AssignmentExplanationSummaryRead:
    explanation = assignment.explanation or {}
    origins = []
    for origin in explanation.get("origins", []):
        origins.append(
            {
                "type": origin.get("type", "persisted_policy_link"),
                "group_name": origin.get("group_name"),
                "matched_clauses": [
                    {
                        "conditions": [
                            _display_condition(condition)
                            for condition in clause.get("conditions", [])
                        ]
                    }
                    for clause in origin.get("matched_clauses", [])
                ],
            }
        )
    selection = explanation.get("selection") or {}
    return AssignmentExplanationSummaryRead.model_validate(
        {
            "reason": explanation.get("reason")
            or (
                "manual_override"
                if assignment.source_override_id is not None
                else "policy"
            ),
            "policy": explanation.get("policy"),
            "origins": origins,
            "selection": {
                "priority": selection.get("priority"),
                "replaced_policy_assignments": selection.get(
                    "replaced_policy_assignments", []
                ),
            },
            "override": explanation.get("override"),
        }
    )


def _current_assignment_read(
    assignment: EmployeeAssignment,
) -> CurrentAssignmentRead:
    return CurrentAssignmentRead(
        id=assignment.id,
        value=assignment.value,
        source_policy_version_id=assignment.source_policy_version_id,
        source_override_id=assignment.source_override_id,
        explanation=_display_explanation(assignment),
        assignment_field_definition=_assignment_field_summary(assignment),
    )


def _assignment_history_read(
    assignment: EmployeeAssignment,
) -> AssignmentHistoryRead:
    return AssignmentHistoryRead(
        id=assignment.id,
        value=assignment.value,
        source_type=(
            "override" if assignment.source_override_id is not None else "policy"
        ),
        effective_from=assignment.effective_from,
        effective_until=assignment.effective_until,
        assignment_field_definition=_assignment_field_summary(assignment),
    )


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create(
    data: EmployeeCreate,
    session: DatabaseSession,
    actor: AuditActor,
    visibility: EmployeeScope,
) -> Employee:
    require_employee_creation_scope(session, visibility, data.manager_id)
    return create_employee(session, data, actor)


@router.get("", response_model=list[EmployeeDirectoryRead])
def list_all(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    search: Annotated[str | None, Query(max_length=200)] = None,
    state: Annotated[str | None, Query(max_length=2)] = None,
    department: Annotated[str | None, Query(max_length=100)] = None,
    employee_type: Annotated[str | None, Query(max_length=100)] = None,
    location: Annotated[str | None, Query(max_length=200)] = None,
    manager_id: Annotated[int | None, Query(gt=0)] = None,
    has_manager: bool | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
) -> list[EmployeeDirectoryRead]:
    statement = visibility.apply(select(Employee))
    if search:
        pattern = f"%{search.strip()}%"
        predicates = [
            Employee.name.ilike(pattern),
            Employee.state.ilike(pattern),
            Employee.department.ilike(pattern),
            Employee.employee_type.ilike(pattern),
            Employee.location.ilike(pattern),
        ]
        matching_codes = matching_state_codes(search)
        if matching_codes:
            predicates.append(Employee.state.in_(matching_codes))
        searched_id = _search_employee_id(search)
        if searched_id is not None:
            predicates.append(Employee.id == searched_id)
        statement = statement.where(or_(*predicates))
    if state is not None:
        try:
            state = normalize_state_code(state)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
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
    employees = paginate_scalars(
        session,
        statement.order_by(Employee.id),
        pagination,
        response,
    )
    if not employees:
        return []

    effective_at = current_datetime()
    count_statement = (
        select(
            EmployeeAssignment.employee_id,
            func.count(EmployeeAssignment.id),
        )
        .where(
            EmployeeAssignment.employee_id.in_(
                [employee.id for employee in employees]
            ),
            EmployeeAssignment.effective_from <= effective_at,
            or_(
                EmployeeAssignment.effective_until.is_(None),
                EmployeeAssignment.effective_until > effective_at,
            ),
        )
        .group_by(EmployeeAssignment.employee_id)
    )
    count_statement = field_visibility.apply(
        count_statement,
        EmployeeAssignment.assignment_field_definition_id,
    )
    counts = dict(session.execute(count_statement).tuples().all())

    return [
        EmployeeDirectoryRead(
            **EmployeeRead.model_validate(employee).model_dump(),
            active_assignment_count=int(counts.get(employee.id, 0)),
        )
        for employee in employees
    ]


@router.get(
    "/manager-candidates",
    response_model=list[EmployeeManagerCandidateRead],
)
def manager_candidates(
    session: DatabaseSession,
    visibility: EmployeeScope,
    search: Annotated[str | None, Query(max_length=200)] = None,
    employee_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[EmployeeManagerCandidateRead]:
    """Return a bounded, minimal set of valid manager choices."""
    if employee_id is None and not (
        visibility.unrestricted or visibility.can_create_reports
    ):
        return []

    excluded_ids: set[int] = set()
    if employee_id is not None:
        visible_employee_or_404(session, visibility, employee_id)
        excluded_ids = {employee_id, *get_descendant_ids(session, employee_id)}

    statement = visibility.apply(
        select(Employee.id, Employee.name, Employee.department),
        Employee.id,
    )
    if excluded_ids:
        statement = statement.where(Employee.id.not_in(excluded_ids))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        predicates = [
            Employee.name.ilike(pattern),
            Employee.department.ilike(pattern),
        ]
        searched_id = _search_employee_id(search)
        if searched_id is not None:
            predicates.append(Employee.id == searched_id)
        statement = statement.where(or_(*predicates))

    rows = session.execute(
        statement.order_by(Employee.name, Employee.id).limit(limit)
    ).all()
    return [
        EmployeeManagerCandidateRead(
            id=employee_id,
            label=(
                f"{name} · {department} · "
                f"#{str(employee_id).zfill(4)}"
            ),
        )
        for employee_id, name, department in rows
    ]


@router.get("/reference-data", response_model=EmployeeReferenceDataRead)
def reference_data(
    session: DatabaseSession,
    visibility: EmployeeScope,
) -> EmployeeReferenceDataRead:
    statement = visibility.apply(
        select(Employee.department, Employee.employee_type),
        Employee.id,
    ).distinct()
    rows = session.execute(statement).all()
    return EmployeeReferenceDataRead(
        departments=sorted({department for department, _ in rows}),
        employee_types=sorted({employee_type for _, employee_type in rows}),
        states=STATES,
    )


@router.get("/{employee_id}", response_model=EmployeeDetailRead)
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


@router.get("/{employee_id}/assignments", response_model=list[CurrentAssignmentRead])
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
) -> list[CurrentAssignmentRead]:
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
    return [
        _current_assignment_read(assignment)
        for assignment in paginate_scalars(session, statement, pagination, response)
    ]


@router.get(
    "/{employee_id}/assignments/history",
    response_model=list[AssignmentHistoryRead],
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
) -> list[AssignmentHistoryRead]:
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
    return [
        _assignment_history_read(assignment)
        for assignment in paginate_scalars(session, statement, pagination, response)
    ]


@router.get(
    "/{employee_id}/overrides/options",
    response_model=list[AssignmentFieldOverrideOptionRead],
)
def override_options(
    employee_id: int,
    session: DatabaseSession,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
) -> list[AssignmentFieldDefinition]:
    visible_employee_or_404(session, visibility, employee_id)
    statement = field_visibility.apply(
        select(AssignmentFieldDefinition),
        AssignmentFieldDefinition.id,
    )
    return list(session.scalars(statement.order_by(AssignmentFieldDefinition.id)))


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
