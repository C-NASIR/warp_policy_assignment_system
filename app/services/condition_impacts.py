from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConditionFieldDefinition, ConditionFieldDependency, Employee
from app.services.org_chart import get_descendant_ids


class ConditionImpactError(ValueError):
    pass


@dataclass(frozen=True)
class EmployeeMutation:
    employee_id: int
    changed_columns: frozenset[str]
    before: Mapping[str, Any]
    after: Mapping[str, Any]


ImpactResolver = Callable[[Session, EmployeeMutation], set[int]]


def _changed_employee(_: Session, mutation: EmployeeMutation) -> set[int]:
    return {mutation.employee_id}


def _old_and_new_managers(_: Session, mutation: EmployeeMutation) -> set[int]:
    return {
        manager_id
        for manager_id in (
            mutation.before.get("manager_id"),
            mutation.after.get("manager_id"),
        )
        if isinstance(manager_id, int)
    }


def _moved_subtree(session: Session, mutation: EmployeeMutation) -> set[int]:
    if session.get(Employee, mutation.employee_id) is None:
        return set()
    return {
        mutation.employee_id,
        *get_descendant_ids(session, mutation.employee_id),
    }


IMPACT_RESOLVERS: dict[str, ImpactResolver] = {
    "changed_employee": _changed_employee,
    "old_and_new_managers": _old_and_new_managers,
    "moved_subtree": _moved_subtree,
}


def find_impacted_employee_ids(
    session: Session,
    mutation: EmployeeMutation,
) -> set[int]:
    """Resolve dependency metadata into existing employees needing reconciliation."""
    if not mutation.changed_columns:
        return set()
    resolver_keys = set(
        session.scalars(
            select(ConditionFieldDependency.impact_resolver_key)
            .join(ConditionFieldDependency.condition_field_definition)
            .where(
                ConditionFieldDefinition.active.is_(True),
                ConditionFieldDependency.source_table == "employees",
                ConditionFieldDependency.source_column.in_(mutation.changed_columns),
            )
            .distinct()
        )
    )
    impacted: set[int] = set()
    for resolver_key in resolver_keys:
        resolver = IMPACT_RESOLVERS.get(resolver_key)
        if resolver is None:
            raise ConditionImpactError(
                f"Unsupported condition impact resolver: {resolver_key}"
            )
        impacted.update(resolver(session, mutation))
    if not impacted:
        return set()
    return set(session.scalars(select(Employee.id).where(Employee.id.in_(impacted))))
