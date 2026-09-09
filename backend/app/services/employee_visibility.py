from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import Integer, Select, and_, cast, func, not_, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models import AuditLog, Employee, Role, User, UserRole
from app.services.auth import AuthenticatedPrincipal
from app.services.org_chart import get_descendant_ids


@dataclass(frozen=True)
class EmployeeVisibility:
    """The employee rows visible to one authenticated principal."""

    unrestricted: bool
    employee_ids: frozenset[int] = frozenset()
    can_create_reports: bool = False

    def can_access(self, employee_id: int) -> bool:
        return self.unrestricted or employee_id in self.employee_ids

    def apply(self, statement: Select, employee_column=Employee.id) -> Select:
        if self.unrestricted:
            return statement
        return statement.where(employee_column.in_(self.employee_ids))


def employee_visibility(
    session: Session,
    principal: AuthenticatedPrincipal,
) -> EmployeeVisibility:
    """Resolve role scopes on every request so access changes take effect immediately."""
    if principal.authentication_method != "human_session":
        return EmployeeVisibility(unrestricted=True, can_create_reports=True)
    if principal.user_id is None:
        return EmployeeVisibility(unrestricted=False)

    user = session.get(User, principal.user_id)
    if user is None:
        return EmployeeVisibility(unrestricted=False)
    if user.is_root:
        return EmployeeVisibility(unrestricted=True, can_create_reports=True)

    scopes = set(
        session.scalars(
            select(Role.employee_scope)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
    )
    if "all" in scopes:
        return EmployeeVisibility(unrestricted=True, can_create_reports=True)
    if user.employee_id is None:
        return EmployeeVisibility(unrestricted=False)

    visible_ids: set[int] = set()
    if "self" in scopes or "reporting_tree" in scopes:
        visible_ids.add(user.employee_id)
    if "reporting_tree" in scopes:
        visible_ids.update(get_descendant_ids(session, user.employee_id))
    return EmployeeVisibility(
        unrestricted=False,
        employee_ids=frozenset(visible_ids),
        can_create_reports="reporting_tree" in scopes,
    )


def visible_employee_or_404(
    session: Session,
    visibility: EmployeeVisibility,
    employee_id: int,
) -> Employee:
    if not visibility.can_access(employee_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )
    return employee


def require_employee_creation_scope(
    session: Session,
    visibility: EmployeeVisibility,
    manager_id: int | None,
) -> None:
    if visibility.unrestricted:
        return
    if (
        not visibility.can_create_reports
        or manager_id is None
        or not visibility.can_access(manager_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "The new employee must report to an employee within your visible "
                "reporting tree"
            ),
        )
    visible_employee_or_404(session, visibility, manager_id)


def apply_audit_visibility(
    statement: Select,
    visibility: EmployeeVisibility,
) -> Select:
    """Hide audit events whose employee subject is outside the caller's scope."""
    if visibility.unrestricted:
        return statement

    before_employee_id = cast(AuditLog.before, JSONB)["employee_id"].astext.cast(
        Integer
    )
    after_employee_id = cast(AuditLog.after, JSONB)["employee_id"].astext.cast(
        Integer
    )
    json_employee_id = func.coalesce(after_employee_id, before_employee_id)
    employee_snapshot_types = {"EmployeeAssignment", "EmployeeOverride"}
    group_membership_event = and_(
        AuditLog.entity_type == "Group",
        AuditLog.action.in_({"employee_added", "employee_removed"}),
    )
    linked_user_event = and_(
        AuditLog.entity_type == "User",
        json_employee_id.is_not(None),
    )
    employee_related = or_(
        AuditLog.entity_type == "Employee",
        AuditLog.entity_type.in_(employee_snapshot_types),
        group_membership_event,
        linked_user_event,
    )
    visible_ids = set(visibility.employee_ids)
    if not visible_ids:
        return statement.where(not_(employee_related))
    visible_event = or_(
        and_(
            AuditLog.entity_type == "Employee",
            AuditLog.entity_id.in_(visible_ids),
        ),
        and_(
            AuditLog.entity_type.in_(employee_snapshot_types),
            json_employee_id.in_(visible_ids),
        ),
        and_(group_membership_event, json_employee_id.in_(visible_ids)),
        and_(
            linked_user_event,
            or_(before_employee_id.is_(None), before_employee_id.in_(visible_ids)),
            or_(after_employee_id.is_(None), after_employee_id.in_(visible_ids)),
        ),
    )
    return statement.where(or_(not_(employee_related), visible_event))
