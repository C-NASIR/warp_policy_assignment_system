from dataclasses import dataclass
from datetime import date
from itertools import groupby
from typing import Any, Mapping

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
from app.services.policy_matching import PolicyMatch, PolicyMatchOrigin


class PolicyConflictError(Exception):
    pass


@dataclass(frozen=True)
class ResolvedAssignment:
    assignment_field_definition_id: int
    value: str
    source_policy_version_id: int
    explanation: dict[str, Any] | None = None


def resolve_employee_assignments(
    session: Session,
    employee: Employee,
    evaluation_date: date | None = None,
) -> list[ResolvedAssignment]:
    """Resolve values from an employee's persisted policy-link projection."""
    policy_ids = set(
        session.scalars(
            select(EmployeePolicy.policy_id).where(
                EmployeePolicy.employee_id == employee.id
            )
        )
    )
    return resolve_policy_assignments(session, policy_ids, evaluation_date)


def resolve_policy_assignments(
    session: Session,
    policy_ids: set[int] | list[int] | tuple[int, ...],
    evaluation_date: date | None = None,
    policy_matches: Mapping[int, PolicyMatch] | None = None,
) -> list[ResolvedAssignment]:
    """Resolve values from an explicitly calculated set of policy identities."""
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
            joinedload(PolicyFieldValue.policy_version).joinedload(
                PolicyVersion.policy
            ),
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
            resolved.append(
                _resolve_one(
                    assignment_field_definition,
                    field_candidates,
                    policy_matches,
                )
            )
        else:
            resolved.extend(
                _resolve_many(
                    assignment_field_definition,
                    field_candidates,
                    policy_matches,
                )
            )
    return resolved


def _resolve_one(
    field: AssignmentFieldDefinition,
    candidates: list[PolicyFieldValue],
    policy_matches: Mapping[int, PolicyMatch] | None,
) -> ResolvedAssignment:
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
    return ResolvedAssignment(
        field.id,
        winner.value,
        winner.policy_version_id,
        _policy_explanation(field, winner, candidates, policy_matches),
    )


def _resolve_many(
    field: AssignmentFieldDefinition,
    candidates: list[PolicyFieldValue],
    policy_matches: Mapping[int, PolicyMatch] | None,
) -> list[ResolvedAssignment]:
    # Ordering selects the highest-priority, lowest-id source when policies duplicate a value.
    unique: dict[str, PolicyFieldValue] = {}
    for candidate in candidates:
        unique.setdefault(candidate.value, candidate)
    return [
        ResolvedAssignment(
            item.assignment_field_definition_id,
            item.value,
            item.policy_version_id,
            _policy_explanation(
                field,
                item,
                [candidate for candidate in candidates if candidate.value == item.value],
                policy_matches,
            ),
        )
        for item in unique.values()
    ]


def _policy_explanation(
    field: AssignmentFieldDefinition,
    winner: PolicyFieldValue,
    candidates: list[PolicyFieldValue],
    policy_matches: Mapping[int, PolicyMatch] | None,
) -> dict[str, Any]:
    version = winner.policy_version
    match = policy_matches.get(version.policy_id) if policy_matches else None
    candidate_summaries = []
    for candidate in candidates:
        selected = candidate is winner
        if selected:
            outcome = "selected"
        elif candidate.value == winner.value:
            outcome = "duplicate_value"
        else:
            outcome = "lower_priority"
        candidate_version = candidate.policy_version
        candidate_match = (
            policy_matches.get(candidate_version.policy_id)
            if policy_matches
            else None
        )
        candidate_summaries.append(
            {
                "policy_id": candidate_version.policy_id,
                "policy_name": candidate_version.policy.name,
                "policy_version_id": candidate_version.id,
                "version_number": candidate_version.version_number,
                "value": candidate.value,
                "priority": candidate_version.priority,
                "selected": selected,
                "outcome": outcome,
                "origins": _origins(candidate_match),
            }
        )
    return {
        "reason": "policy",
        "policy": {
            "id": version.policy_id,
            "name": version.policy.name,
        },
        "policy_version": {
            "id": version.id,
            "version_number": version.version_number,
        },
        "origins": _origins(match),
        "selection": {
            "field": field.name,
            "cardinality": field.cardinality,
            "strategy": (
                field.conflict_resolution
                if field.cardinality == "one"
                else "set_union"
            ),
            "source_selection": (
                "highest_priority_then_lowest_version_id"
                if field.cardinality == "many"
                else None
            ),
            "priority": version.priority,
            "candidates": candidate_summaries,
        },
    }


def _origins(match: PolicyMatch | None) -> list[dict[str, Any]]:
    if match is None:
        return [{"type": "persisted_policy_link"}]
    return [_origin(origin) for origin in match.origins]


def _origin(origin: PolicyMatchOrigin) -> dict[str, Any]:
    if origin.type == "group":
        return {
            "type": "group",
            "group_id": origin.group_id,
            "group_name": origin.group_name,
        }
    return {
        "type": "condition_match",
        "matched_clauses": [
            {
                "clause_id": clause.clause_id,
                "conditions": [
                    {
                        "field": condition.field,
                        "operator": condition.operator,
                        "expected": condition.expected,
                        "actual": condition.actual,
                        "result": condition.result,
                    }
                    for condition in clause.conditions
                ],
            }
            for clause in origin.matched_clauses
        ],
    }
