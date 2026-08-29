from datetime import date

from sqlalchemy import String, and_, case, cast, delete, func, inspect, or_, select
from sqlalchemy.orm import Session

from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Employee,
    EmployeeGroupMembership,
    EmployeePolicy,
    GroupPolicy,
)


class EmployeePolicyRefreshError(ValueError):
    pass


def find_matching_policy_ids(session: Session, employee_id: int) -> list[int]:
    """Return deduplicated direct and group-inherited policy IDs."""
    direct_policy_ids = find_direct_matching_policy_ids(session, employee_id)
    group_policy_ids = session.scalars(
        select(GroupPolicy.policy_id)
        .join(
            EmployeeGroupMembership,
            EmployeeGroupMembership.group_id == GroupPolicy.group_id,
        )
        .where(EmployeeGroupMembership.employee_id == employee_id)
        .distinct()
    )
    return sorted(set(direct_policy_ids).union(group_policy_ids))


def find_direct_matching_policy_ids(session: Session, employee_id: int) -> list[int]:
    """Return policies having a compiled clause satisfied by the employee."""
    employee_fields = [column for column in inspect(Employee).columns if not column.primary_key]
    condition_matches = or_(
        *(_condition_matches_employee_column(column) for column in employee_fields)
    )
    matched_count = func.sum(case((condition_matches, 1), else_=0))

    statement = (
        select(CompiledPolicyClause.policy_id)
        .join(CompiledPolicyClause.conditions)
        .join(Employee, Employee.id == employee_id)
        .group_by(CompiledPolicyClause.id, CompiledPolicyClause.policy_id)
        .having(func.count(CompiledPolicyCondition.id) == matched_count)
        .distinct()
        .order_by(CompiledPolicyClause.policy_id)
    )
    return list(session.scalars(statement))


def _condition_matches_employee_column(column):
    """Build type-aware comparisons for one employee fact column."""
    employee_value = getattr(Employee, column.key)

    # Dates are persisted as ISO-8601 values, so their string ordering is their
    # chronological ordering. Integers must remain numeric for < and <=.
    if column.type.python_type is date:
        comparable_employee_value = cast(employee_value, String)
        comparable_condition_value = CompiledPolicyCondition.value
    elif column.type.python_type is int:
        comparable_employee_value = employee_value
        comparable_condition_value = cast(CompiledPolicyCondition.value, column.type)
    else:
        comparable_employee_value = employee_value
        comparable_condition_value = CompiledPolicyCondition.value

    return and_(
        CompiledPolicyCondition.field == column.key,
        or_(
            and_(
                CompiledPolicyCondition.operator == "=",
                cast(employee_value, String) == CompiledPolicyCondition.value,
            ),
            and_(
                CompiledPolicyCondition.operator == "<",
                comparable_employee_value < comparable_condition_value,
            ),
            and_(
                CompiledPolicyCondition.operator == "<=",
                comparable_employee_value <= comparable_condition_value,
            ),
        ),
    )


def refresh_employee_policies(session: Session, employee_id: int) -> list[EmployeePolicy]:
    """Replace an employee's policy links with their current compiled-policy matches."""
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise EmployeePolicyRefreshError(f"Employee {employee_id} not found")

    policy_ids = find_matching_policy_ids(session, employee_id)
    session.execute(delete(EmployeePolicy).where(EmployeePolicy.employee_id == employee_id))
    session.flush()

    links = [EmployeePolicy(employee_id=employee_id, policy_id=policy_id) for policy_id in policy_ids]
    session.add_all(links)
    session.flush()
    session.expire(employee, ["policies"])
    return links
