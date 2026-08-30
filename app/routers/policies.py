from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import AuditActor, DatabaseSession
from app.models import (
    Condition,
    ConditionGroup,
    ConditionGroupCondition,
    FieldDefinition,
    Policy,
    PolicyFieldValue,
    PolicyVersion,
)
from app.schemas import (
    ConditionGroupCreate,
    PolicyCreate,
    PolicyRead,
    PolicyUpdate,
    PolicyVersionCreate,
    PolicyVersionRead,
)
from app.services.audit import record_audit_log, snapshot_entity
from app.services.policy_compiler import (
    PolicyCompilationError,
    compile_policy_version_clauses,
)
from app.services.policy_reconciliation import refresh_employees_affected_by_policy
from app.services.scheduled_reconciliations import sync_policy_version_schedules
from app.services.policy_versions import create_policy_version

router = APIRouter(prefix="/policies", tags=["policies"])


def _query():
    return select(Policy).options(
        selectinload(Policy.versions).selectinload(PolicyVersion.values)
    )


def _version_query():
    return select(PolicyVersion).options(selectinload(PolicyVersion.values))


def _policy_or_404(session: DatabaseSession, policy_id: int) -> Policy:
    policy = session.scalar(_query().where(Policy.id == policy_id))
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return policy


def _validate_field_definitions(session: DatabaseSession, values) -> None:
    field_ids = {item.field_definition_id for item in values}
    existing_ids = set(session.scalars(select(FieldDefinition.id).where(FieldDefinition.id.in_(field_ids))))
    missing_ids = sorted(field_ids - existing_ids)
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Field definitions not found: {missing_ids}")


def _build_canonical_condition_tree(data: ConditionGroupCreate) -> ConditionGroup:
    return ConditionGroup(
        logical_operator=data.logical_operator,
        condition_links=[
            ConditionGroupCondition(
                condition=Condition(field=item.field, operator=item.operator, value=item.value)
            )
            for item in data.conditions
        ],
        child_groups=[_build_canonical_condition_tree(child) for child in data.child_groups],
    )


def _collect_condition_groups(root: ConditionGroup) -> list[ConditionGroup]:
    return [
        root,
        *(
            group
            for child in root.child_groups
            for group in _collect_condition_groups(child)
        ),
    ]


def _create_version(
    session: DatabaseSession,
    policy: Policy,
    data: PolicyVersionCreate,
    actor: str,
) -> PolicyVersion:
    _validate_field_definitions(session, data.values)
    canonical_root = _build_canonical_condition_tree(data.condition_group)
    try:
        compiled_clauses = compile_policy_version_clauses(canonical_root)
    except PolicyCompilationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    version = create_policy_version(
        session,
        policy,
        priority=data.priority,
        effective_from=data.effective_from,
        effective_until=data.effective_until,
        created_by=data.created_by,
        values=[PolicyFieldValue(**item.model_dump()) for item in data.values],
        condition_groups=_collect_condition_groups(canonical_root),
        compiled_clauses=compiled_clauses,
        actor=actor,
    )
    sync_policy_version_schedules(session, policy)
    return version


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
    _create_version(session, policy, data, actor)
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
    version = _create_version(session, policy, data, actor)
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
