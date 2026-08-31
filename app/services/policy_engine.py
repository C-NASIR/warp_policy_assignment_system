from dataclasses import dataclass
from datetime import date
from itertools import groupby

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AssignmentFieldDefinition,
    Employee,
    EmployeePolicy,
    PolicyFieldValue,
    PolicyVersion,
)
from app.services.policy_versions import get_effective_policy_versions


class PolicyConflictError(Exception):
    pass


@dataclass(frozen=True)
class ResolvedAssignment:
    assignment_field_definition_id: int
    value: str
    source_policy_version_id: int


def resolve_employee_assignments(
    session: Session,
    employee: Employee,
    evaluation_date: date | None = None,
) -> list[ResolvedAssignment]:
    policy_ids = set(
        session.scalars(
            select(EmployeePolicy.policy_id).where(
                EmployeePolicy.employee_id == employee.id
            )
        )
    )
    effective_versions = get_effective_policy_versions(
        session,
        policy_ids,
        evaluation_date,
    )
    if not effective_versions:
        return []
    version_ids = {version.id for version in effective_versions.values()}
    candidates = session.scalars(
        select(PolicyFieldValue)
        .join(PolicyFieldValue.policy_version)
        .where(PolicyFieldValue.policy_version_id.in_(version_ids))
        .options(
            joinedload(PolicyFieldValue.policy_version),
            joinedload(PolicyFieldValue.assignment_field_definition),
        )
        .order_by(
            PolicyFieldValue.assignment_field_definition_id,
            PolicyVersion.priority.desc(),
            PolicyVersion.id,
        )
    ).all()

    resolved: list[ResolvedAssignment] = []
    for _, field_candidates_iter in groupby(candidates, key=lambda item: item.assignment_field_definition_id):
        field_candidates = list(field_candidates_iter)
        assignment_field_definition: AssignmentFieldDefinition = field_candidates[0].assignment_field_definition
        if assignment_field_definition.cardinality == "one":
            resolved.append(_resolve_one(assignment_field_definition, field_candidates))
        else:
            resolved.extend(_resolve_many(field_candidates))
    return resolved


def _resolve_one(field: AssignmentFieldDefinition, candidates: list[PolicyFieldValue]) -> ResolvedAssignment:
    highest_priority = candidates[0].policy_version.priority
    winners = [
        candidate
        for candidate in candidates
        if candidate.policy_version.priority == highest_priority
    ]
    values = {candidate.value for candidate in winners}
    if len(values) > 1:
        raise PolicyConflictError(
            f"Conflicting values for field '{field.name}' at priority {highest_priority}: {sorted(values)}"
        )
    winner = winners[0]
    return ResolvedAssignment(field.id, winner.value, winner.policy_version_id)


def _resolve_many(candidates: list[PolicyFieldValue]) -> list[ResolvedAssignment]:
    # Ordering selects the highest-priority, lowest-id source when policies duplicate a value.
    unique: dict[str, PolicyFieldValue] = {}
    for candidate in candidates:
        unique.setdefault(candidate.value, candidate)
    return [
        ResolvedAssignment(
            item.assignment_field_definition_id,
            item.value,
            item.policy_version_id,
        )
        for item in unique.values()
    ]
