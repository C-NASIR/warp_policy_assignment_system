from dataclasses import dataclass
from itertools import groupby

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Employee,
    EmployeePolicy,
    FieldDefinition,
    Policy,
    PolicyFieldValue,
)


class PolicyConflictError(Exception):
    pass


@dataclass(frozen=True)
class ResolvedAssignment:
    field_definition_id: int
    value: str
    source_policy_id: int


def resolve_assignments(session: Session, employee: Employee) -> list[ResolvedAssignment]:
    candidates = session.scalars(
        select(PolicyFieldValue)
        .join(PolicyFieldValue.policy)
        .join(EmployeePolicy, EmployeePolicy.policy_id == Policy.id)
        .where(EmployeePolicy.employee_id == employee.id)
        .options(joinedload(PolicyFieldValue.policy), joinedload(PolicyFieldValue.field_definition))
        .order_by(PolicyFieldValue.field_definition_id, Policy.priority.desc(), Policy.id)
    ).all()

    resolved: list[ResolvedAssignment] = []
    for _, field_candidates_iter in groupby(candidates, key=lambda item: item.field_definition_id):
        field_candidates = list(field_candidates_iter)
        field_definition: FieldDefinition = field_candidates[0].field_definition
        if field_definition.cardinality == "one":
            resolved.append(_resolve_one(field_definition, field_candidates))
        else:
            resolved.extend(_resolve_many(field_candidates))
    return resolved


def _resolve_one(field: FieldDefinition, candidates: list[PolicyFieldValue]) -> ResolvedAssignment:
    highest_priority = candidates[0].policy.priority
    winners = [candidate for candidate in candidates if candidate.policy.priority == highest_priority]
    values = {candidate.value for candidate in winners}
    if len(values) > 1:
        raise PolicyConflictError(
            f"Conflicting values for field '{field.name}' at priority {highest_priority}: {sorted(values)}"
        )
    winner = winners[0]
    return ResolvedAssignment(field.id, winner.value, winner.policy_id)


def _resolve_many(candidates: list[PolicyFieldValue]) -> list[ResolvedAssignment]:
    # Ordering selects the highest-priority, lowest-id source when policies duplicate a value.
    unique: dict[str, PolicyFieldValue] = {}
    for candidate in candidates:
        unique.setdefault(candidate.value, candidate)
    return [ResolvedAssignment(item.field_definition_id, item.value, item.policy_id) for item in unique.values()]
