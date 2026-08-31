from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.dates import current_date
from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Employee,
    EmployeeGroupMembership,
    EmployeePolicy,
    GroupPolicy,
)
from app.services.condition_fields import (
    ConditionEvaluationContext,
    evaluate_condition,
)
from app.services.policy_versions import get_effective_policy_versions


class EmployeePolicyRefreshError(ValueError):
    pass


def find_matching_policy_ids(
    session: Session,
    employee_id: int,
    evaluation_date: date | None = None,
) -> list[int]:
    """Return deduplicated direct and group-inherited policy IDs."""
    direct_policy_ids = find_direct_matching_policy_ids(
        session,
        employee_id,
        evaluation_date,
    )
    group_policy_candidates = set(
        session.scalars(
            select(GroupPolicy.policy_id)
            .join(
                EmployeeGroupMembership,
                EmployeeGroupMembership.group_id == GroupPolicy.group_id,
            )
            .where(EmployeeGroupMembership.employee_id == employee_id)
            .distinct()
        )
    )
    group_policy_ids = get_effective_policy_versions(
        session,
        group_policy_candidates,
        evaluation_date,
    )
    return sorted(set(direct_policy_ids).union(group_policy_ids))


def find_direct_matching_policy_ids(
    session: Session,
    employee_id: int,
    evaluation_date: date | None = None,
) -> list[int]:
    """Return policies whose effective version has a satisfied compiled clause."""
    effective_versions = get_effective_policy_versions(
        session,
        evaluation_date=evaluation_date,
    )
    if not effective_versions:
        return []
    versions_by_id = {version.id: version for version in effective_versions.values()}
    employee = session.get(Employee, employee_id)
    if employee is None:
        return []
    effective_on = evaluation_date or current_date()
    context = ConditionEvaluationContext(
        session=session,
        employee=employee,
        evaluation_date=effective_on,
    )
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
    matched_version_ids = {
        clause.policy_version_id
        for clause in clauses
        if clause.conditions
        and all(
            evaluate_condition(
                context,
                condition.condition_field_definition,
                condition.operator,
                condition.value,
            )
            for condition in clause.conditions
        )
    }
    return sorted(
        versions_by_id[version_id].policy_id
        for version_id in matched_version_ids
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
