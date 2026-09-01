from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import AuditActor, DatabaseSession
from app.models import (
    Condition,
    ConditionGroup,
    ConditionGroupCondition,
    Policy,
    PolicyVersion,
)
from app.schemas import (
    PolicyCreate,
    PolicyRead,
    PolicyUpdate,
    PolicyVersionCreate,
    PolicyVersionRead,
)
from app.services.audit import record_audit_log, snapshot_entity
from app.services.policy_authoring import create_policy_version_from_input
from app.services.policy_reconciliation import refresh_employees_affected_by_policy
from app.services.scheduled_reconciliations import sync_policy_version_schedules
from app.services.tenure_scheduling import sync_all_employee_tenure_schedules

router = APIRouter(prefix="/policies", tags=["policies"])


def _query():
    return select(Policy).options(
        selectinload(Policy.versions).selectinload(PolicyVersion.values),
        selectinload(Policy.versions)
        .selectinload(PolicyVersion.condition_groups)
        .selectinload(ConditionGroup.child_groups),
        selectinload(Policy.versions)
        .selectinload(PolicyVersion.condition_groups)
        .selectinload(ConditionGroup.condition_links)
        .selectinload(ConditionGroupCondition.condition)
        .selectinload(Condition.condition_field_definition),
    )


def _version_query():
    return select(PolicyVersion).options(
        selectinload(PolicyVersion.values),
        selectinload(PolicyVersion.condition_groups).selectinload(
            ConditionGroup.child_groups
        ),
        selectinload(PolicyVersion.condition_groups)
        .selectinload(ConditionGroup.condition_links)
        .selectinload(ConditionGroupCondition.condition)
        .selectinload(Condition.condition_field_definition),
    )


def _policy_or_404(session: DatabaseSession, policy_id: int) -> Policy:
    policy = session.scalar(_query().where(Policy.id == policy_id))
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return policy


@router.post("", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
def create(data: PolicyCreate, session: DatabaseSession, actor: AuditActor) -> Policy:
    policy = Policy(name=data.name, status=data.status)
    session.add(policy)
    session.flush()
    record_audit_log(
        session,
        actor=actor,
        entity_type="Policy",
        entity_id=policy.id,
        action="created",
        before=None,
        after=snapshot_entity(policy),
    )
    create_policy_version_from_input(session, policy, data, actor)
    refresh_employees_affected_by_policy(session, policy)
    return session.scalar(_query().where(Policy.id == policy.id))


@router.get("", response_model=list[PolicyRead])
def list_all(session: DatabaseSession) -> list[Policy]:
    return list(session.scalars(_query().order_by(Policy.id)))


@router.get("/{policy_id}", response_model=PolicyRead)
def get(policy_id: int, session: DatabaseSession) -> Policy:
    return _policy_or_404(session, policy_id)


@router.patch("/{policy_id}", response_model=PolicyRead)
def patch(
    policy_id: int,
    data: PolicyUpdate,
    session: DatabaseSession,
    actor: AuditActor,
) -> Policy:
    policy = _policy_or_404(session, policy_id)
    before = snapshot_entity(policy)
    if data.name is not None:
        policy.name = data.name
    if data.status is not None:
        policy.status = data.status
    session.flush()
    after = snapshot_entity(policy)
    if before != after:
        action = (
            "archived"
            if before["status"] != "archived" and after["status"] == "archived"
            else "changed"
        )
        record_audit_log(
            session,
            actor=actor,
            entity_type="Policy",
            entity_id=policy.id,
            action=action,
            before=before,
            after=after,
        )
        if before["status"] != after["status"]:
            sync_policy_version_schedules(session, policy)
            sync_all_employee_tenure_schedules(session)
            refresh_employees_affected_by_policy(session, policy)
    return session.scalar(_query().where(Policy.id == policy.id))


@router.get("/{policy_id}/versions", response_model=list[PolicyVersionRead])
def list_versions(policy_id: int, session: DatabaseSession) -> list[PolicyVersion]:
    _policy_or_404(session, policy_id)
    return list(
        session.scalars(
            _version_query()
            .where(PolicyVersion.policy_id == policy_id)
            .order_by(PolicyVersion.version_number)
        )
    )


@router.post(
    "/{policy_id}/versions",
    response_model=PolicyVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def add_version(
    policy_id: int,
    data: PolicyVersionCreate,
    session: DatabaseSession,
    actor: AuditActor,
) -> PolicyVersion:
    policy = _policy_or_404(session, policy_id)
    version = create_policy_version_from_input(session, policy, data, actor)
    refresh_employees_affected_by_policy(session, policy)
    return session.scalar(_version_query().where(PolicyVersion.id == version.id))


@router.get(
    "/{policy_id}/versions/{version_id}",
    response_model=PolicyVersionRead,
)
def get_version(
    policy_id: int,
    version_id: int,
    session: DatabaseSession,
) -> PolicyVersion:
    _policy_or_404(session, policy_id)
    version = session.scalar(
        _version_query().where(
            PolicyVersion.id == version_id,
            PolicyVersion.policy_id == policy_id,
        )
    )
    if version is None:
        raise HTTPException(
            status_code=404,
            detail=f"Policy version {version_id} not found for policy {policy_id}",
        )
    return version
