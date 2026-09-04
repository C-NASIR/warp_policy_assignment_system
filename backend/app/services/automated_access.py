from __future__ import annotations

from collections.abc import Collection
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AutomatedUserRole, PolicyRoleGrant, Role, User
from app.services.audit import record_audit_log
from app.services.policy_versions import get_effective_policy_versions


def reconcile_automated_roles(
    session: Session,
    *,
    employee_id: int,
    policy_ids: Collection[int],
    evaluation_date: date,
    timestamp: datetime,
    actor: str = "system",
) -> None:
    """Replace only policy-derived grants; explicit assignments remain protected."""
    user = session.scalar(select(User).where(User.employee_id == employee_id))
    if user is None or user.is_root:
        return

    effective_versions = get_effective_policy_versions(
        session,
        policy_ids,
        evaluation_date,
    )
    version_ids = {version.id for version in effective_versions.values()}
    desired = (
        {
            (role_id, version_id)
            for role_id, version_id in session.execute(
                select(
                    PolicyRoleGrant.role_id,
                    PolicyRoleGrant.policy_version_id,
                ).where(PolicyRoleGrant.policy_version_id.in_(version_ids))
            )
        }
        if version_ids
        else set()
    )
    current = {
        (link.role_id, link.source_policy_version_id): link
        for link in session.scalars(
            select(AutomatedUserRole).where(AutomatedUserRole.user_id == user.id)
        )
    }

    role_names = {
        role.id: role.name
        for role in session.scalars(
            select(Role).where(
                Role.id.in_({role_id for role_id, _ in desired | set(current)})
            )
        )
    }
    for key, link in current.items():
        if key in desired:
            continue
        session.delete(link)
        record_audit_log(
            session,
            actor=actor,
            entity_type="UserRole",
            entity_id=user.id,
            action="automated_revoked",
            before={
                "user_id": user.id,
                "employee_id": employee_id,
                "role_id": link.role_id,
                "role_name": role_names.get(link.role_id),
                "source_policy_version_id": link.source_policy_version_id,
                "source": "policy",
            },
            after=None,
            timestamp=timestamp,
        )

    for role_id, version_id in sorted(desired - set(current)):
        session.add(
            AutomatedUserRole(
                user_id=user.id,
                role_id=role_id,
                source_policy_version_id=version_id,
            )
        )
        record_audit_log(
            session,
            actor=actor,
            entity_type="UserRole",
            entity_id=user.id,
            action="automated_granted",
            before=None,
            after={
                "user_id": user.id,
                "employee_id": employee_id,
                "role_id": role_id,
                "role_name": role_names.get(role_id),
                "source_policy_version_id": version_id,
                "source": "policy",
            },
            timestamp=timestamp,
        )
    session.flush()


def clear_automated_roles_for_user(
    session: Session,
    user: User,
    *,
    actor: str,
    timestamp: datetime,
) -> None:
    links = list(
        session.scalars(
            select(AutomatedUserRole).where(AutomatedUserRole.user_id == user.id)
        )
    )
    role_names = {
        role.id: role.name
        for role in session.scalars(
            select(Role).where(Role.id.in_({link.role_id for link in links}))
        )
    }
    for link in links:
        session.delete(link)
        record_audit_log(
            session,
            actor=actor,
            entity_type="UserRole",
            entity_id=user.id,
            action="automated_revoked",
            before={
                "user_id": user.id,
                "employee_id": user.employee_id,
                "role_id": link.role_id,
                "role_name": role_names.get(link.role_id),
                "source_policy_version_id": link.source_policy_version_id,
                "source": "policy",
            },
            after=None,
            timestamp=timestamp,
        )
    session.flush()
