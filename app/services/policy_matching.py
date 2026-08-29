from sqlalchemy import String, and_, case, cast, delete, func, inspect, or_, select
from sqlalchemy.orm import Session

from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Employee,
    EmployeePolicy,
)


class EmployeePolicyRefreshError(ValueError):
    pass


def find_matching_policy_ids(session: Session, employee_id: int) -> list[int]:
    """Return policy IDs having at least one fully satisfied compiled clause."""
    employee_fields = [column for column in inspect(Employee).columns if not column.primary_key]
    condition_matches = and_(
        CompiledPolicyCondition.operator == "=",
        or_(
            *(
                and_(
                    CompiledPolicyCondition.field == column.key,
                    CompiledPolicyCondition.value == cast(getattr(Employee, column.key), String),
                )
                for column in employee_fields
            )
        ),
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
