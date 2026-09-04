from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.dates import current_date, current_datetime, start_of_day
from app.models import (
    AssignmentFieldDefinition,
    Employee,
    EmployeeAssignment,
    EmployeeOverride,
    Policy,
)
from app.schemas import (
    AssignmentFieldDefinitionRead,
    AssignmentFieldSummaryRead,
    AssignmentSummaryRead,
    ImpactSummaryConflictRead,
    PolicyFieldImpactSummaryRead,
    PolicyImpactSummaryRead,
)
from app.services.assignment_resolution import resolve_employee_assignments_for_date
from app.services.policy_engine import PolicyConflictError, resolve_policy_assignments
from app.services.policy_matching import find_policy_matches
from app.services.policy_versions import get_effective_policy_version

_MAX_VALUE_SAMPLES = 20
_MAX_CONFLICT_SAMPLES = 100


@dataclass(frozen=True)
class _SummaryAssignment:
    employee_id: int
    assignment_field_definition_id: int
    value: str
    source_policy_version_id: int | None
    source_override_id: int | None


@dataclass
class _AssignmentFieldAccumulator:
    employee_ids: set[int] = field(default_factory=set)
    values: set[str] = field(default_factory=set)
    assignment_count: int = 0
    policy_assignment_count: int = 0
    override_assignment_count: int = 0


@dataclass
class _PolicyFieldAccumulator:
    configured_values: set[str] = field(default_factory=set)
    selected_employee_ids: set[int] = field(default_factory=set)
    suppressed_employee_ids: set[int] = field(default_factory=set)
    selected_assignment_count: int = 0
    suppressed_assignment_count: int = 0


def build_assignment_summary(
    session: Session,
    evaluation_date: date,
    *,
    employee_id: int | None = None,
    visible_employee_ids: set[int] | None = None,
    visible_assignment_field_ids: set[int] | None = None,
) -> AssignmentSummaryRead:
    employee_statement = select(Employee.id).order_by(Employee.id)
    if employee_id is not None:
        employee_statement = employee_statement.where(Employee.id == employee_id)
    if visible_employee_ids is not None:
        employee_statement = employee_statement.where(
            Employee.id.in_(visible_employee_ids)
        )
    employee_ids = list(session.scalars(employee_statement))
    assignments: list[_SummaryAssignment] = []
    conflicts: list[ImpactSummaryConflictRead] = []
    conflicted_employee_count = 0

    today = current_date()
    if evaluation_date < today:
        mode = "recorded_history"
        effective_at = start_of_day(evaluation_date)
        assignments = _persisted_assignments(
            session,
            employee_ids,
            effective_at,
            visible_assignment_field_ids,
        )
    elif evaluation_date == today:
        mode = "current_persisted"
        assignments = _persisted_assignments(
            session,
            employee_ids,
            current_datetime(),
            visible_assignment_field_ids,
        )
    else:
        mode = "calculated_future"
        employees = list(
            session.scalars(
                select(Employee)
                .where(Employee.id.in_(employee_ids))
                .order_by(Employee.id)
            )
        )
        for employee in employees:
            try:
                resolution = resolve_employee_assignments_for_date(
                    session,
                    employee,
                    evaluation_date,
                )
            except PolicyConflictError as exc:
                conflicted_employee_count += 1
                if len(conflicts) < _MAX_CONFLICT_SAMPLES:
                    conflicts.append(_impact_conflict(employee.id, exc))
                continue
            assignments.extend(
                _SummaryAssignment(
                    employee_id=employee.id,
                    assignment_field_definition_id=(
                        assignment.assignment_field_definition_id
                    ),
                    value=assignment.value,
                    source_policy_version_id=assignment.source_policy_version_id,
                    source_override_id=assignment.source_override_id,
                )
                for assignment in resolution.assignments
                if visible_assignment_field_ids is None
                or assignment.assignment_field_definition_id
                in visible_assignment_field_ids
            )

    field_statement = select(AssignmentFieldDefinition)
    if visible_assignment_field_ids is not None:
        field_statement = field_statement.where(
            AssignmentFieldDefinition.id.in_(visible_assignment_field_ids)
        )
    fields_by_id = {
        definition.id: definition
        for definition in session.scalars(
            field_statement.order_by(AssignmentFieldDefinition.id)
        )
    }
    field_accumulators: dict[int, _AssignmentFieldAccumulator] = {}
    employees_with_assignments: set[int] = set()
    policy_assignment_count = 0
    override_assignment_count = 0
    for assignment in assignments:
        employees_with_assignments.add(assignment.employee_id)
        accumulator = field_accumulators.setdefault(
            assignment.assignment_field_definition_id,
            _AssignmentFieldAccumulator(),
        )
        accumulator.employee_ids.add(assignment.employee_id)
        accumulator.values.add(assignment.value)
        accumulator.assignment_count += 1
        if assignment.source_policy_version_id is not None:
            policy_assignment_count += 1
            accumulator.policy_assignment_count += 1
        else:
            override_assignment_count += 1
            accumulator.override_assignment_count += 1

    field_summaries = [
        _assignment_field_summary(fields_by_id[field_id], accumulator)
        for field_id, accumulator in sorted(field_accumulators.items())
    ]
    resolved_employee_count = len(employee_ids) - conflicted_employee_count
    return AssignmentSummaryRead(
        scope="employee" if employee_id is not None else "population",
        employee_id=employee_id,
        evaluation_date=evaluation_date,
        mode=mode,
        complete=conflicted_employee_count == 0,
        employee_count=len(employee_ids),
        employees_with_assignments=len(employees_with_assignments),
        employees_without_assignments=(
            resolved_employee_count - len(employees_with_assignments)
        ),
        assignment_count=len(assignments),
        policy_assignment_count=policy_assignment_count,
        override_assignment_count=override_assignment_count,
        field_count=len(field_summaries),
        fields=field_summaries,
        conflicted_employee_count=conflicted_employee_count,
        conflicts=conflicts,
        conflicts_truncated=conflicted_employee_count > len(conflicts),
    )


def build_policy_impact_summary(
    session: Session,
    policy: Policy,
    evaluation_date: date,
    *,
    visible_employee_ids: set[int] | None = None,
) -> PolicyImpactSummaryRead:
    employee_statement = select(Employee).order_by(Employee.id)
    if visible_employee_ids is not None:
        employee_statement = employee_statement.where(
            Employee.id.in_(visible_employee_ids)
        )
    employees = list(session.scalars(employee_statement))
    effective_version = get_effective_policy_version(
        session,
        policy.id,
        evaluation_date,
    )
    mode = "current" if evaluation_date == current_date() else "calculated_future"
    if effective_version is None:
        return PolicyImpactSummaryRead(
            policy_id=policy.id,
            policy_name=policy.name,
            policy_status=policy.status,
            evaluation_date=evaluation_date,
            mode=mode,
            calculation_basis="live_resolution_current_employee_facts",
            complete=True,
            effective=False,
            effective_policy_version_id=None,
            effective_version_number=None,
            total_employee_count=len(employees),
            matched_employee_count=0,
            direct_match_employee_count=0,
            group_match_employee_count=0,
            direct_and_group_match_employee_count=0,
            selected_employee_count=0,
            selected_assignment_count=0,
            matched_without_selected_assignment_count=0,
            suppressed_by_override_employee_count=0,
            suppressed_by_override_assignment_count=0,
            fields=[],
            conflicted_employee_count=0,
            conflicts=[],
            conflicts_truncated=False,
        )

    field_ids = {
        value.assignment_field_definition_id for value in effective_version.values
    }
    fields_by_id = {
        definition.id: definition
        for definition in session.scalars(
            select(AssignmentFieldDefinition)
            .where(AssignmentFieldDefinition.id.in_(field_ids))
            .order_by(AssignmentFieldDefinition.id)
        )
    }
    field_accumulators = {
        field_id: _PolicyFieldAccumulator(
            configured_values={
                value.value
                for value in effective_version.values
                if value.assignment_field_definition_id == field_id
            }
        )
        for field_id in sorted(field_ids)
    }

    matched_employee_count = 0
    direct_match_employee_count = 0
    group_match_employee_count = 0
    direct_and_group_match_employee_count = 0
    selected_employee_count = 0
    selected_assignment_count = 0
    matched_without_selected_assignment_count = 0
    suppressed_employee_count = 0
    suppressed_assignment_count = 0
    conflicted_employee_count = 0
    conflicts: list[ImpactSummaryConflictRead] = []

    for employee in employees:
        policy_matches = find_policy_matches(session, employee.id, evaluation_date)
        policy_match = policy_matches.get(policy.id)
        if policy_match is None:
            continue
        matched_employee_count += 1
        has_direct_origin = any(
            origin.type == "condition_match" for origin in policy_match.origins
        )
        has_group_origin = any(
            origin.type == "group" for origin in policy_match.origins
        )
        direct_match_employee_count += int(has_direct_origin)
        group_match_employee_count += int(has_group_origin)
        direct_and_group_match_employee_count += int(
            has_direct_origin and has_group_origin
        )
        try:
            resolved = resolve_policy_assignments(
                session,
                tuple(policy_matches),
                evaluation_date,
                policy_matches,
            )
        except PolicyConflictError as exc:
            conflicted_employee_count += 1
            if len(conflicts) < _MAX_CONFLICT_SAMPLES:
                conflicts.append(_impact_conflict(employee.id, exc))
            continue

        policy_assignments = [
            assignment
            for assignment in resolved
            if assignment.source_policy_version_id == effective_version.id
        ]
        overridden_field_ids = set(
            session.scalars(
                select(EmployeeOverride.assignment_field_definition_id).where(
                    EmployeeOverride.employee_id == employee.id,
                    EmployeeOverride.retired_at.is_(None),
                )
            )
        )
        selected = [
            assignment
            for assignment in policy_assignments
            if assignment.assignment_field_definition_id not in overridden_field_ids
        ]
        suppressed = [
            assignment
            for assignment in policy_assignments
            if assignment.assignment_field_definition_id in overridden_field_ids
        ]
        if selected:
            selected_employee_count += 1
            selected_assignment_count += len(selected)
        else:
            matched_without_selected_assignment_count += 1
        if suppressed:
            suppressed_employee_count += 1
            suppressed_assignment_count += len(suppressed)

        for assignment in selected:
            accumulator = field_accumulators[
                assignment.assignment_field_definition_id
            ]
            accumulator.selected_employee_ids.add(employee.id)
            accumulator.selected_assignment_count += 1
        for assignment in suppressed:
            accumulator = field_accumulators[
                assignment.assignment_field_definition_id
            ]
            accumulator.suppressed_employee_ids.add(employee.id)
            accumulator.suppressed_assignment_count += 1

    field_summaries = [
        _policy_field_summary(fields_by_id[field_id], field_accumulators[field_id])
        for field_id in sorted(field_accumulators)
    ]
    return PolicyImpactSummaryRead(
        policy_id=policy.id,
        policy_name=policy.name,
        policy_status=policy.status,
        evaluation_date=evaluation_date,
        mode=mode,
        calculation_basis="live_resolution_current_employee_facts",
        complete=conflicted_employee_count == 0,
        effective=True,
        effective_policy_version_id=effective_version.id,
        effective_version_number=effective_version.version_number,
        total_employee_count=len(employees),
        matched_employee_count=matched_employee_count,
        direct_match_employee_count=direct_match_employee_count,
        group_match_employee_count=group_match_employee_count,
        direct_and_group_match_employee_count=direct_and_group_match_employee_count,
        selected_employee_count=selected_employee_count,
        selected_assignment_count=selected_assignment_count,
        matched_without_selected_assignment_count=(
            matched_without_selected_assignment_count
        ),
        suppressed_by_override_employee_count=suppressed_employee_count,
        suppressed_by_override_assignment_count=suppressed_assignment_count,
        fields=field_summaries,
        conflicted_employee_count=conflicted_employee_count,
        conflicts=conflicts,
        conflicts_truncated=conflicted_employee_count > len(conflicts),
    )


def _persisted_assignments(
    session: Session,
    employee_ids: list[int],
    effective_at: datetime,
    visible_assignment_field_ids: set[int] | None,
) -> list[_SummaryAssignment]:
    if not employee_ids:
        return []
    statement = (
        select(EmployeeAssignment)
        .where(
            EmployeeAssignment.employee_id.in_(employee_ids),
            EmployeeAssignment.effective_from <= effective_at,
            or_(
                EmployeeAssignment.effective_until.is_(None),
                EmployeeAssignment.effective_until > effective_at,
            ),
        )
        .options(joinedload(EmployeeAssignment.assignment_field_definition))
        .order_by(EmployeeAssignment.employee_id, EmployeeAssignment.id)
    )
    if visible_assignment_field_ids is not None:
        statement = statement.where(
            EmployeeAssignment.assignment_field_definition_id.in_(
                visible_assignment_field_ids
            )
        )
    rows = session.scalars(statement)
    return [
        _SummaryAssignment(
            employee_id=row.employee_id,
            assignment_field_definition_id=row.assignment_field_definition_id,
            value=row.value,
            source_policy_version_id=row.source_policy_version_id,
            source_override_id=row.source_override_id,
        )
        for row in rows
    ]


def _assignment_field_summary(
    definition: AssignmentFieldDefinition,
    accumulator: _AssignmentFieldAccumulator,
) -> AssignmentFieldSummaryRead:
    values = sorted(accumulator.values)
    return AssignmentFieldSummaryRead(
        assignment_field_definition=AssignmentFieldDefinitionRead.model_validate(
            definition
        ),
        assigned_employee_count=len(accumulator.employee_ids),
        assignment_count=accumulator.assignment_count,
        policy_assignment_count=accumulator.policy_assignment_count,
        override_assignment_count=accumulator.override_assignment_count,
        distinct_value_count=len(values),
        value_samples=values[:_MAX_VALUE_SAMPLES],
        values_truncated=len(values) > _MAX_VALUE_SAMPLES,
    )


def _policy_field_summary(
    definition: AssignmentFieldDefinition,
    accumulator: _PolicyFieldAccumulator,
) -> PolicyFieldImpactSummaryRead:
    values = sorted(accumulator.configured_values)
    return PolicyFieldImpactSummaryRead(
        assignment_field_definition=AssignmentFieldDefinitionRead.model_validate(
            definition
        ),
        configured_value_count=len(values),
        configured_value_samples=values[:_MAX_VALUE_SAMPLES],
        configured_values_truncated=len(values) > _MAX_VALUE_SAMPLES,
        selected_employee_count=len(accumulator.selected_employee_ids),
        selected_assignment_count=accumulator.selected_assignment_count,
        suppressed_by_override_employee_count=len(
            accumulator.suppressed_employee_ids
        ),
        suppressed_by_override_assignment_count=(
            accumulator.suppressed_assignment_count
        ),
    )


def _impact_conflict(
    employee_id: int,
    exc: PolicyConflictError,
) -> ImpactSummaryConflictRead:
    field_id = exc.metadata.get("assignment_field_definition_id")
    if not isinstance(field_id, int):
        field_id = None
    return ImpactSummaryConflictRead(
        employee_id=employee_id,
        code="policy_conflict",
        message=str(exc),
        assignment_field_definition_id=field_id,
        assignment_field_name=exc.assignment_field_name,
        metadata=jsonable_encoder(exc.metadata),
    )
