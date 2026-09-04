from collections.abc import Collection
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.dates import current_date
from app.models import (
    CompiledPolicyClause,
    ConditionGroup,
    Policy,
    PolicyFieldValue,
    PolicyRoleGrant,
    PolicyVersion,
)
from app.services.audit import record_audit_log, snapshot_policy_version


class PolicyVersionOverlapError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        policy_id: int | None = None,
        effective_from: date | None = None,
        effective_until: date | None = None,
        overlapping_policy_version_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = {
            "policy_id": policy_id,
            "effective_from": effective_from,
            "effective_until": effective_until,
            "overlapping_policy_version_id": overlapping_policy_version_id,
        }


class EffectivePolicyVersionConflictError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        policy_id: int,
        evaluation_date: date,
    ) -> None:
        super().__init__(message)
        self.metadata = {
            "policy_id": policy_id,
            "evaluation_date": evaluation_date,
        }


def create_policy_version(
    session: Session,
    policy: Policy,
    *,
    priority: int,
    effective_from: date,
    effective_until: date | None,
    created_by: str | None,
    values: list[PolicyFieldValue],
    role_grants: list[PolicyRoleGrant],
    condition_groups: list[ConditionGroup],
    compiled_clauses: list[CompiledPolicyClause],
    actor: str = "system",
) -> PolicyVersion:
    if effective_until is not None and effective_until < effective_from:
        raise PolicyVersionOverlapError(
            "effective_until cannot be before effective_from",
            policy_id=policy.id,
            effective_from=effective_from,
            effective_until=effective_until,
        )
    session.scalar(
        select(Policy.id)
        .where(Policy.id == policy.id)
        .with_for_update()
    )
    prior_version = session.scalar(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy.id)
        .order_by(PolicyVersion.version_number.desc())
        .limit(1)
    )
    before = snapshot_policy_version(prior_version) if prior_version is not None else None
    _close_prior_open_ended_version(session, policy.id, effective_from)
    _reject_overlapping_range(
        session,
        policy.id,
        effective_from,
        effective_until,
    )
    current_version_number = session.scalar(
        select(func.coalesce(func.max(PolicyVersion.version_number), 0)).where(
            PolicyVersion.policy_id == policy.id
        )
    )
    next_version_number = (current_version_number or 0) + 1
    version = PolicyVersion(
        policy=policy,
        version_number=next_version_number,
        priority=priority,
        effective_from=effective_from,
        effective_until=effective_until,
        created_by=created_by,
        values=values,
        role_grants=role_grants,
        condition_groups=condition_groups,
        compiled_clauses=compiled_clauses,
    )
    session.add(version)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="PolicyVersion",
        entity_id=version.id,
        action="created",
        before=before,
        after=snapshot_policy_version(version),
    )
    return version


def get_effective_policy_version(
    session: Session,
    policy_id: int,
    evaluation_date: date | None = None,
) -> PolicyVersion | None:
    return get_effective_policy_versions(
        session,
        [policy_id],
        evaluation_date,
    ).get(policy_id)


def get_effective_policy_versions(
    session: Session,
    policy_ids: Collection[int] | None = None,
    evaluation_date: date | None = None,
) -> dict[int, PolicyVersion]:
    effective_on = evaluation_date or current_date()
    if policy_ids is not None and not policy_ids:
        return {}

    statement = (
        select(PolicyVersion)
        .join(PolicyVersion.policy)
        .where(
            Policy.status == "active",
            PolicyVersion.effective_from <= effective_on,
            or_(
                PolicyVersion.effective_until.is_(None),
                PolicyVersion.effective_until >= effective_on,
            ),
        )
        .options(selectinload(PolicyVersion.values))
        .order_by(PolicyVersion.policy_id, PolicyVersion.version_number)
    )
    if policy_ids is not None:
        statement = statement.where(PolicyVersion.policy_id.in_(policy_ids))

    effective_versions: dict[int, PolicyVersion] = {}
    for version in session.scalars(statement):
        if version.policy_id in effective_versions:
            raise EffectivePolicyVersionConflictError(
                f"Policy {version.policy_id} has multiple versions effective on "
                f"{effective_on}",
                policy_id=version.policy_id,
                evaluation_date=effective_on,
            )
        effective_versions[version.policy_id] = version
    return effective_versions


def _reject_overlapping_range(
    session: Session,
    policy_id: int,
    effective_from: date,
    effective_until: date | None,
) -> None:
    overlap = session.scalar(
        select(PolicyVersion.id)
        .where(
            PolicyVersion.policy_id == policy_id,
            PolicyVersion.effective_from <= (effective_until or date.max),
            or_(
                PolicyVersion.effective_until.is_(None),
                PolicyVersion.effective_until >= effective_from,
            ),
        )
        .limit(1)
    )
    if overlap is not None:
        end = effective_until.isoformat() if effective_until else "open-ended"
        raise PolicyVersionOverlapError(
            f"Policy {policy_id} already has a version overlapping "
            f"{effective_from.isoformat()} through {end}",
            policy_id=policy_id,
            effective_from=effective_from,
            effective_until=effective_until,
            overlapping_policy_version_id=overlap,
        )


def _close_prior_open_ended_version(
    session: Session,
    policy_id: int,
    next_effective_from: date,
) -> None:
    prior_open_version = session.scalar(
        select(PolicyVersion)
        .where(
            PolicyVersion.policy_id == policy_id,
            PolicyVersion.effective_until.is_(None),
            PolicyVersion.effective_from < next_effective_from,
        )
        .order_by(PolicyVersion.effective_from.desc())
        .limit(1)
    )
    if prior_open_version is not None:
        prior_open_version.effective_until = next_effective_from - timedelta(days=1)
        session.flush()
