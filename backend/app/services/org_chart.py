from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models import Employee


class EmployeeManagerNotFoundError(ValueError):
    pass


class EmployeeHierarchyConflictError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        employee_id: int | None = None,
        manager_id: int | None = None,
        reason: str,
    ) -> None:
        super().__init__(message)
        self.metadata = {
            "employee_id": employee_id,
            "manager_id": manager_id,
            "reason": reason,
        }


def validate_manager_assignment(
    session: Session,
    *,
    employee_id: int | None,
    manager_id: int | None,
) -> None:
    if manager_id is None:
        return
    if employee_id is not None and manager_id == employee_id:
        raise EmployeeHierarchyConflictError(
            "An employee cannot manage themselves",
            employee_id=employee_id,
            manager_id=manager_id,
            reason="self_management",
        )
    if session.get(Employee, manager_id) is None:
        raise EmployeeManagerNotFoundError(f"Manager employee {manager_id} not found")
    if employee_id is not None and employee_id in get_ancestor_ids(session, manager_id):
        raise EmployeeHierarchyConflictError(
            f"Assigning manager {manager_id} to employee {employee_id} would "
            "create a reporting cycle",
            employee_id=employee_id,
            manager_id=manager_id,
            reason="reporting_cycle",
        )


def get_ancestor_ids(session: Session, employee_id: int) -> set[int]:
    """Return every manager above an employee, nearest or distant.

    UNION (rather than UNION ALL) also makes this terminate safely if corrupt
    data contains a cycle.
    """
    ancestors = (
        select(Employee.manager_id.label("employee_id"))
        .where(
            Employee.id == employee_id,
            Employee.manager_id.is_not(None),
        )
        .cte("employee_ancestors", recursive=True)
    )
    parent = aliased(Employee)
    ancestors = ancestors.union(
        select(parent.manager_id.label("employee_id"))
        .join(ancestors, parent.id == ancestors.c.employee_id)
        .where(parent.manager_id.is_not(None))
    )
    return set(session.scalars(select(ancestors.c.employee_id)))


def get_descendant_ids(session: Session, employee_id: int) -> set[int]:
    """Return every direct and indirect report below an employee."""
    descendants = (
        select(Employee.id.label("employee_id"))
        .where(Employee.manager_id == employee_id)
        .cte("employee_descendants", recursive=True)
    )
    report = aliased(Employee)
    descendants = descendants.union(
        select(report.id.label("employee_id")).join(
            descendants,
            report.manager_id == descendants.c.employee_id,
        )
    )
    return set(session.scalars(select(descendants.c.employee_id)))


def employee_is_manager(session: Session, employee_id: int) -> bool:
    return (
        session.scalar(
            select(
                select(Employee.id).where(Employee.manager_id == employee_id).exists()
            )
        )
        is True
    )


def employee_direct_report_count(session: Session, employee_id: int) -> int:
    return (
        session.scalar(
            select(func.count(Employee.id)).where(Employee.manager_id == employee_id)
        )
        or 0
    )


def employee_management_level(session: Session, employee_id: int) -> int:
    """Return the number of reporting hops from the employee to a root employee."""
    return len(get_ancestor_ids(session, employee_id))
