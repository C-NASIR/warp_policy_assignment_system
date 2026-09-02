from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.dates import current_date
from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Employee,
    EmployeeGroupMembership,
    EmployeePolicy,
    Group,
    GroupPolicy,
)
from app.services.condition_fields import (
    ConditionEvaluationContext,
    evaluate_condition_with_evidence,
)
from app.services.policy_versions import get_effective_policy_versions


class EmployeePolicyRefreshError(ValueError):
    pass


@dataclass(frozen=True)
class ConditionMatchEvidence:
    field: str
    operator: str
    expected: Any
    actual: Any
    result: bool


@dataclass(frozen=True)
class ClauseMatchEvidence:
    clause_id: int
    conditions: tuple[ConditionMatchEvidence, ...]


@dataclass(frozen=True)
class PolicyMatchOrigin:
    type: Literal["condition_match", "group"]
    matched_clauses: tuple[ClauseMatchEvidence, ...] = ()
    group_id: int | None = None
    group_name: str | None = None


@dataclass(frozen=True)
class PolicyMatch:
    policy_id: int
    policy_version_id: int
    policy_name: str
    version_number: int
    priority: int
    origins: tuple[PolicyMatchOrigin, ...]


def find_matching_policy_ids(
    session: Session,
    employee_id: int,
    evaluation_date: date | None = None,
) -> list[int]:
    """Return deduplicated direct and group-inherited policy IDs."""
    return sorted(find_policy_matches(session, employee_id, evaluation_date))


def find_policy_matches(
    session: Session,
    employee_id: int,
    evaluation_date: date | None = None,
) -> dict[int, PolicyMatch]:
    """Return date-effective policy matches with condition and group evidence."""
    employee = session.get(Employee, employee_id)
    if employee is None:
        return {}
    effective_versions = get_effective_policy_versions(
        session,
        evaluation_date=evaluation_date,
    )
    if not effective_versions:
        return {}
    versions_by_id = {version.id: version for version in effective_versions.values()}
    effective_on = evaluation_date or current_date()
    context = ConditionEvaluationContext(
        session=session,
        employee=employee,
        evaluation_date=effective_on,
    )
    matched_clauses: dict[int, list[ClauseMatchEvidence]] = {}
    clauses = list(
        session.scalars(
            select(CompiledPolicyClause)
            .where(CompiledPolicyClause.policy_version_id.in_(versions_by_id))
            .options(
                selectinload(CompiledPolicyClause.conditions).selectinload(
                    CompiledPolicyCondition.condition_field_definition
                )
            )
            .order_by(CompiledPolicyClause.policy_version_id, CompiledPolicyClause.id)
        )
    )
    for clause in clauses:
        if not clause.conditions:
            continue
        condition_evidence: list[ConditionMatchEvidence] = []
        for condition in clause.conditions:
            evaluation = evaluate_condition_with_evidence(
                context,
                condition.condition_field_definition,
                condition.operator,
                condition.value,
            )
            condition_evidence.append(
                ConditionMatchEvidence(
                    field=condition.field,
                    operator=condition.operator,
                    expected=evaluation.expected,
                    actual=evaluation.actual,
                    result=evaluation.result,
                )
            )
        if all(item.result for item in condition_evidence):
            matched_clauses.setdefault(clause.policy_version_id, []).append(
                ClauseMatchEvidence(
                    clause_id=clause.id,
                    conditions=tuple(condition_evidence),
                )
            )

    origins_by_policy: dict[int, list[PolicyMatchOrigin]] = {}
    for version_id, version_clauses in matched_clauses.items():
        version = versions_by_id[version_id]
        origins_by_policy.setdefault(version.policy_id, []).append(
            PolicyMatchOrigin(
                type="condition_match",
                matched_clauses=tuple(version_clauses),
            )
        )

    group_rows = session.execute(
        select(Group.id, Group.name, GroupPolicy.policy_id)
        .join(
            EmployeeGroupMembership,
            EmployeeGroupMembership.group_id == Group.id,
        )
        .join(GroupPolicy, GroupPolicy.group_id == Group.id)
        .where(EmployeeGroupMembership.employee_id == employee_id)
        .order_by(Group.id, GroupPolicy.policy_id)
    )
    for group_id, group_name, policy_id in group_rows:
        if policy_id not in effective_versions:
            continue
        origins_by_policy.setdefault(policy_id, []).append(
            PolicyMatchOrigin(
                type="group",
                group_id=group_id,
                group_name=group_name,
            )
        )

    return {
        policy_id: PolicyMatch(
            policy_id=policy_id,
            policy_version_id=effective_versions[policy_id].id,
            policy_name=effective_versions[policy_id].policy.name,
            version_number=effective_versions[policy_id].version_number,
            priority=effective_versions[policy_id].priority,
            origins=tuple(origins),
        )
        for policy_id, origins in sorted(origins_by_policy.items())
    }


def find_direct_matching_policy_ids(
    session: Session,
    employee_id: int,
    evaluation_date: date | None = None,
) -> list[int]:
    """Return policies whose effective version has a satisfied compiled clause."""
    return sorted(
        policy_id
        for policy_id, match in find_policy_matches(
            session,
            employee_id,
            evaluation_date,
        ).items()
        if any(origin.type == "condition_match" for origin in match.origins)
    )


def refresh_employee_policies(
    session: Session,
    employee_id: int,
    evaluation_date: date | None = None,
) -> list[EmployeePolicy]:
    """Replace an employee's policy links with their current compiled-policy matches."""
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise EmployeePolicyRefreshError(f"Employee {employee_id} not found")

    policy_ids = find_matching_policy_ids(session, employee_id, evaluation_date)
    return replace_employee_policies(session, employee_id, policy_ids)


def replace_employee_policies(
    session: Session,
    employee_id: int,
    policy_ids: list[int] | tuple[int, ...],
) -> list[EmployeePolicy]:
    """Persist a previously calculated policy-link projection."""
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise EmployeePolicyRefreshError(f"Employee {employee_id} not found")

    session.execute(delete(EmployeePolicy).where(EmployeePolicy.employee_id == employee_id))
    session.flush()

    links = [
        EmployeePolicy(employee_id=employee_id, policy_id=policy_id)
        for policy_id in policy_ids
    ]
    session.add_all(links)
    session.flush()
    session.expire(employee, ["policies"])
    return links
