from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import Integer, Select, and_, cast, exists, func, not_, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models import (
    AssignmentFieldDefinition,
    AuditLog,
    Policy,
    PolicyFieldValue,
    PolicyVersion,
    Role,
    RoleAssignmentFieldScope,
    User,
    UserRole,
)
from app.services.auth import AuthenticatedPrincipal


@dataclass(frozen=True)
class AssignmentFieldVisibility:
    """Assignment output domains visible to one authenticated principal."""

    unrestricted: bool
    assignment_field_ids: frozenset[int] = frozenset()

    def can_access(self, assignment_field_definition_id: int) -> bool:
        return (
            self.unrestricted
            or assignment_field_definition_id in self.assignment_field_ids
        )

    def apply(self, statement: Select, assignment_field_column) -> Select:
        if self.unrestricted:
            return statement
        return statement.where(
            assignment_field_column.in_(self.assignment_field_ids)
        )


def assignment_field_visibility(
    session: Session,
    principal: AuthenticatedPrincipal,
) -> AssignmentFieldVisibility:
    """Union selected domains across roles; any all-domain role wins."""
    if principal.authentication_method != "human_session":
        return AssignmentFieldVisibility(unrestricted=True)
    if principal.user_id is None:
        return AssignmentFieldVisibility(unrestricted=False)

    user = session.get(User, principal.user_id)
    if user is None:
        return AssignmentFieldVisibility(unrestricted=False)
    if user.is_root:
        return AssignmentFieldVisibility(unrestricted=True)

    scopes = set(
        session.scalars(
            select(Role.assignment_field_scope)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
    )
    if "all" in scopes:
        return AssignmentFieldVisibility(unrestricted=True)

    field_ids = frozenset(
        session.scalars(
            select(RoleAssignmentFieldScope.assignment_field_definition_id)
            .join(Role, Role.id == RoleAssignmentFieldScope.role_id)
            .join(UserRole, UserRole.role_id == RoleAssignmentFieldScope.role_id)
            .where(
                UserRole.user_id == user.id,
                Role.assignment_field_scope == "selected",
            )
        )
    )
    return AssignmentFieldVisibility(
        unrestricted=False,
        assignment_field_ids=field_ids,
    )


def visible_assignment_field_or_404(
    session: Session,
    visibility: AssignmentFieldVisibility,
    assignment_field_definition_id: int,
) -> AssignmentFieldDefinition:
    if not visibility.can_access(assignment_field_definition_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Assignment field definition "
                f"{assignment_field_definition_id} not found"
            ),
        )
    assignment_field = session.get(
        AssignmentFieldDefinition,
        assignment_field_definition_id,
    )
    if assignment_field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Assignment field definition "
                f"{assignment_field_definition_id} not found"
            ),
        )
    return assignment_field


def require_unrestricted_assignment_fields(
    visibility: AssignmentFieldVisibility,
) -> None:
    if visibility.unrestricted:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Creating assignment fields requires access to all assignment fields",
    )


def validate_assignment_field_ids(
    session: Session,
    visibility: AssignmentFieldVisibility,
    assignment_field_ids: Iterable[int],
) -> None:
    for field_id in set(assignment_field_ids):
        visible_assignment_field_or_404(session, visibility, field_id)


def visible_policy_condition(visibility: AssignmentFieldVisibility):
    """A policy is visible only when none of its version outputs are hidden."""
    if visibility.unrestricted:
        return True
    hidden_value = (
        select(PolicyFieldValue.policy_version_id)
        .join(
            PolicyVersion,
            PolicyVersion.id == PolicyFieldValue.policy_version_id,
        )
        .where(PolicyVersion.policy_id == Policy.id)
    )
    if visibility.assignment_field_ids:
        hidden_value = hidden_value.where(
            PolicyFieldValue.assignment_field_definition_id.not_in(
                visibility.assignment_field_ids
            )
        )
    return ~exists(hidden_value)


def visible_policy_ids(
    session: Session,
    visibility: AssignmentFieldVisibility,
) -> set[int] | None:
    if visibility.unrestricted:
        return None
    return set(
        session.scalars(
            select(Policy.id).where(visible_policy_condition(visibility))
        )
    )


def require_visible_policy(
    session: Session,
    visibility: AssignmentFieldVisibility,
    policy_id: int,
) -> None:
    if visibility.unrestricted:
        return
    found = session.scalar(
        select(Policy.id).where(
            Policy.id == policy_id,
            visible_policy_condition(visibility),
        )
    )
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )


def apply_assignment_field_audit_visibility(
    session: Session,
    statement: Select,
    visibility: AssignmentFieldVisibility,
) -> Select:
    """Hide audit events tied to assignment domains outside the caller's scope."""
    if visibility.unrestricted:
        return statement

    before_field_id = cast(AuditLog.before, JSONB)[
        "assignment_field_definition_id"
    ].astext.cast(Integer)
    after_field_id = cast(AuditLog.after, JSONB)[
        "assignment_field_definition_id"
    ].astext.cast(Integer)
    json_field_id = func.coalesce(after_field_id, before_field_id)
    before_policy_id = cast(AuditLog.before, JSONB)["policy_id"].astext.cast(
        Integer
    )
    after_policy_id = cast(AuditLog.after, JSONB)["policy_id"].astext.cast(
        Integer
    )
    json_policy_id = func.coalesce(after_policy_id, before_policy_id)

    field_entity = AuditLog.entity_type.in_(
        {"AssignmentFieldDefinition", "EmployeeAssignment", "EmployeeOverride"}
    )
    policy_entity = AuditLog.entity_type == "Policy"
    policy_version_entity = AuditLog.entity_type == "PolicyVersion"
    group_policy_event = and_(
        AuditLog.entity_type == "Group",
        AuditLog.action.in_({"policy_attached", "policy_detached"}),
    )
    domain_related = or_(
        field_entity,
        policy_entity,
        policy_version_entity,
        group_policy_event,
    )

    field_ids = set(visibility.assignment_field_ids)
    policy_ids = visible_policy_ids(session, visibility) or set()
    visible_event = or_(
        and_(
            AuditLog.entity_type == "AssignmentFieldDefinition",
            AuditLog.entity_id.in_(field_ids),
        ),
        and_(
            AuditLog.entity_type.in_({"EmployeeAssignment", "EmployeeOverride"}),
            json_field_id.in_(field_ids),
        ),
        and_(policy_entity, AuditLog.entity_id.in_(policy_ids)),
        and_(policy_version_entity, json_policy_id.in_(policy_ids)),
        and_(group_policy_event, json_policy_id.in_(policy_ids)),
    )
    return statement.where(or_(not_(domain_related), visible_event))
