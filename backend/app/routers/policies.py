from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.dates import current_date
from app.dependencies import (
    AssignmentFieldScope,
    AuditActor,
    Authenticated,
    DatabaseSession,
    EmployeeScope,
)
from app.models import (
    Condition,
    ConditionGroup,
    ConditionGroupCondition,
    Policy,
    PolicyVersion,
)
from app.pagination import Pagination, paginate_scalars
from app.schemas import (
    PolicyCreate,
    PolicyImpactSummaryRead,
    PolicyRead,
    PolicyUpdate,
    PolicyVersionCreate,
    PolicyVersionRead,
)
from app.services.assignment_field_visibility import (
    AssignmentFieldVisibility,
    validate_assignment_field_ids,
    visible_policy_condition,
)
from app.services.audit import record_audit_log, snapshot_entity
from app.services.impact_summaries import build_policy_impact_summary
from app.services.policy_access import (
    policy_read,
    require_policy_permission,
    require_policy_version_create,
)
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


def _policy_or_404(
    session: DatabaseSession,
    policy_id: int,
    visibility: AssignmentFieldVisibility,
) -> Policy:
    policy = session.scalar(
        _query().where(
            Policy.id == policy_id,
            visible_policy_condition(visibility),
        )
    )
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return policy


@router.post("", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
def create(
    data: PolicyCreate,
    session: DatabaseSession,
    actor: AuditActor,
    field_visibility: AssignmentFieldScope,
    principal: Authenticated,
) -> PolicyRead:
    validate_assignment_field_ids(
        session,
        field_visibility,
        (value.assignment_field_definition_id for value in data.values),
    )
    if data.status == "active":
        require_policy_permission(principal, "policies:activate")
    elif data.status == "archived":
        require_policy_permission(principal, "policies:archive")
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
    created = session.scalar(_query().where(Policy.id == policy.id))
    assert created is not None
    return policy_read(principal, created)


@router.get("", response_model=list[PolicyRead])
def list_all(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    field_visibility: AssignmentFieldScope,
    principal: Authenticated,
    search: Annotated[str | None, Query(max_length=200)] = None,
    status_filter: Annotated[
        Literal["draft", "active", "archived"] | None,
        Query(alias="status"),
    ] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[PolicyRead]:
    statement = _query().where(visible_policy_condition(field_visibility))
    if search:
        statement = statement.where(Policy.name.ilike(f"%{search.strip()}%"))
    if status_filter is not None:
        statement = statement.where(Policy.status == status_filter)
    if created_from is not None:
        statement = statement.where(Policy.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(Policy.created_at <= created_to)
    policies = paginate_scalars(
        session,
        statement.order_by(Policy.id),
        pagination,
        response,
    )
    return [policy_read(principal, policy) for policy in policies]


@router.get("/{policy_id}", response_model=PolicyRead)
def get(
    policy_id: int,
    session: DatabaseSession,
    field_visibility: AssignmentFieldScope,
    principal: Authenticated,
) -> PolicyRead:
    return policy_read(
        principal,
        _policy_or_404(session, policy_id, field_visibility),
    )


@router.get(
    "/{policy_id}/impact-summary",
    response_model=PolicyImpactSummaryRead,
)
def impact_summary(
    policy_id: int,
    session: DatabaseSession,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    evaluation_date: date | None = None,
) -> PolicyImpactSummaryRead:
    effective_on = evaluation_date or current_date()
    if effective_on < current_date():
        raise HTTPException(
            status_code=422,
            detail=(
                "Policy impact summaries cannot reconstruct historical employee "
                "facts; evaluation_date must be today or later"
            ),
        )
    return build_policy_impact_summary(
        session,
        _policy_or_404(session, policy_id, field_visibility),
        effective_on,
        visible_employee_ids=(
            None if visibility.unrestricted else set(visibility.employee_ids)
        ),
    )


@router.patch("/{policy_id}", response_model=PolicyRead)
def patch(
    policy_id: int,
    data: PolicyUpdate,
    session: DatabaseSession,
    actor: AuditActor,
    field_visibility: AssignmentFieldScope,
    principal: Authenticated,
) -> PolicyRead:
    policy = _policy_or_404(session, policy_id, field_visibility)
    if data.name is not None or not data.model_fields_set:
        require_policy_permission(principal, "policies:update")
    if data.status == "active":
        require_policy_permission(principal, "policies:activate")
    elif data.status == "archived":
        require_policy_permission(principal, "policies:archive")
    elif data.status == "draft" and policy.status != "draft":
        require_policy_permission(principal, "policies:update")
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
    changed = session.scalar(_query().where(Policy.id == policy.id))
    assert changed is not None
    return policy_read(principal, changed)


@router.get("/{policy_id}/versions", response_model=list[PolicyVersionRead])
def list_versions(
    policy_id: int,
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    field_visibility: AssignmentFieldScope,
    effective_on: date | None = None,
    priority: int | None = None,
    created_by: Annotated[str | None, Query(max_length=200)] = None,
) -> list[PolicyVersion]:
    _policy_or_404(session, policy_id, field_visibility)
    statement = _version_query().where(PolicyVersion.policy_id == policy_id)
    if effective_on is not None:
        statement = statement.where(
            PolicyVersion.effective_from <= effective_on,
            or_(
                PolicyVersion.effective_until.is_(None),
                PolicyVersion.effective_until >= effective_on,
            ),
        )
    if priority is not None:
        statement = statement.where(PolicyVersion.priority == priority)
    if created_by is not None:
        statement = statement.where(PolicyVersion.created_by == created_by)
    return paginate_scalars(
        session,
        statement.order_by(PolicyVersion.version_number),
        pagination,
        response,
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
    field_visibility: AssignmentFieldScope,
    principal: Authenticated,
) -> PolicyVersion:
    policy = _policy_or_404(session, policy_id, field_visibility)
    require_policy_version_create(principal, policy)
    validate_assignment_field_ids(
        session,
        field_visibility,
        (value.assignment_field_definition_id for value in data.values),
    )
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
    field_visibility: AssignmentFieldScope,
) -> PolicyVersion:
    _policy_or_404(session, policy_id, field_visibility)
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
