from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.dates import current_datetime
from app.dependencies import (
    AssignmentFieldScope,
    AuditActor,
    Authenticated,
    DatabaseSession,
    EmployeeScope,
)
from app.error_contract import conflict_issue
from app.models import (
    ApprovedChangeExecution,
    AutomatedUserRole,
    ChangeApprovalRequest,
    Employee,
    EmployeeAssignment,
    EmployeeOverride,
    Policy,
    Role,
    User,
)
from app.schemas import (
    ApprovedChangeExecutionCreate,
    ApprovedChangeExecutionRead,
    AssignmentFieldPreviewChangeRead,
    AssignmentPreviewRead,
    AutomatedRolePreviewChangeRead,
    ChangePreviewCreate,
    ChangePreviewRead,
    EmployeeAssignmentPreviewChangeRead,
    EmployeeCreateChangePreview,
    EmployeeOverrideChangePreview,
    EmployeeUpdateChangePreview,
    GroupMembershipChangePreview,
    PolicyStatusChangePreview,
    PolicyVersionCreateChangePreview,
)
from app.services.access_control import WILDCARD_PERMISSION
from app.services.approval_requests import (
    create_approval_request,
    mark_request_executed,
    require_approved_executor,
)
from app.services.assignment_field_visibility import (
    AssignmentFieldVisibility,
    require_visible_policy,
    validate_assignment_field_ids,
    visible_assignment_field_or_404,
)
from app.services.audit import record_audit_log, snapshot_entity
from app.services.change_approvals import (
    ChangeApprovalConflictError,
    change_precondition_digest,
    issue_change_approval,
    lock_approval_execution,
    preview_digest,
    validate_approval_not_expired,
    validate_approved_change,
    verify_change_approval,
)
from app.services.employee_overrides import (
    EmployeeOverrideConflictError,
    create_employee_override,
    delete_employee_override,
    update_employee_override,
)
from app.services.employee_visibility import (
    EmployeeVisibility,
    require_employee_creation_scope,
    visible_employee_or_404,
)
from app.services.employees import create_employee, update_employee
from app.services.groups import add_employee_to_group, remove_employee_from_group
from app.services.org_chart import EmployeeHierarchyConflictError
from app.services.policy_access import (
    require_policy_permission,
    require_policy_version_create,
)
from app.services.policy_authoring import create_policy_version_from_input
from app.services.policy_engine import PolicyConflictError
from app.services.policy_reconciliation import refresh_employees_affected_by_policy
from app.services.policy_versions import (
    EffectivePolicyVersionConflictError,
    PolicyVersionOverlapError,
)
from app.services.scheduled_reconciliations import sync_policy_version_schedules
from app.services.tenure_scheduling import sync_all_employee_tenure_schedules

router = APIRouter(prefix="/change-previews", tags=["change previews"])
execution_router = APIRouter(
    prefix="/change-executions",
    tags=["change executions"],
)

_APPROVAL_UNAVAILABLE_WARNING = (
    "Approved execution is unavailable because CHANGE_APPROVAL_SECRET is not "
    "configured"
)


@dataclass
class _MutationContext:
    included_employee_ids: set[int] = field(default_factory=set)
    proposed_employee_ids: set[int] = field(default_factory=set)
    proposed_policy_version_ids: set[int] = field(default_factory=set)
    proposed_override_ids: set[int] = field(default_factory=set)
    resources: dict[str, int] = field(default_factory=dict)


@router.post("", response_model=ChangePreviewRead)
def preview(
    data: ChangePreviewCreate,
    session: DatabaseSession,
    actor: AuditActor,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    principal: Authenticated,
) -> ChangePreviewRead:
    """Simulate one supported mutation and roll back every resulting write."""
    requires_human_approval = _requires_human_approval(data, principal)
    if (
        requires_human_approval
        and isinstance(data, PolicyVersionCreateChangePreview)
    ):
        data.version.created_by = principal.subject
    _validate_change_scope(
        session,
        data,
        field_visibility,
        visibility,
        principal,
    )
    savepoint = session.begin_nested()
    try:
        approved_precondition_digest = change_precondition_digest(
            session,
            data,
            lock=False,
        )
        before = _current_assignments(
            session,
            visibility=visibility,
            field_visibility=field_visibility,
        )
        before_access = _current_automated_roles(session, visibility)
        context = _MutationContext()
        try:
            _apply_change(
                session,
                data,
                actor,
                context,
                visibility,
            )
            session.flush()
            after = _current_assignments(
                session,
                proposed_policy_version_ids=context.proposed_policy_version_ids,
                proposed_override_ids=context.proposed_override_ids,
                visibility=visibility,
                field_visibility=field_visibility,
                proposed_employee_ids=context.proposed_employee_ids,
            )
            changes = _assignment_changes(
                session,
                before,
                after,
                context,
            )
            after_access = _current_automated_roles(session, visibility)
            access_changes = _automated_role_changes(
                before_access,
                after_access,
                context.proposed_policy_version_ids,
            )
            response = ChangePreviewRead(
                change_type=data.type,
                valid=True,
                affected_employee_count=sum(
                    bool(item.added or item.removed or item.changed)
                    for item in changes
                ),
                changes=changes,
                affected_user_count=len(
                    {item.user_id for item in access_changes}
                ),
                access_changes=access_changes,
                conflicts=[],
                warnings=[],
            )
            if not requires_human_approval:
                response.approval = issue_change_approval(
                    data,
                    response,
                    approved_precondition_digest,
                )
                if response.approval is None:
                    response.warnings.append(_APPROVAL_UNAVAILABLE_WARNING)
        except (
            EffectivePolicyVersionConflictError,
            EmployeeHierarchyConflictError,
            EmployeeOverrideConflictError,
            PolicyConflictError,
            PolicyVersionOverlapError,
        ) as exc:
            response = ChangePreviewRead(
                change_type=data.type,
                valid=False,
                affected_employee_count=0,
                changes=[],
                conflicts=[
                    _preview_conflict_issue(exc, context)
                ],
                warnings=[],
            )
    finally:
        if savepoint.is_active:
            savepoint.rollback()
        session.expire_all()
    if response.valid and requires_human_approval:
        try:
            request = create_approval_request(
                session,
                change=data,
                preview=response,
                precondition_digest=approved_precondition_digest,
                principal=principal,
            )
        except HTTPException as exc:
            if exc.status_code != status.HTTP_503_SERVICE_UNAVAILABLE:
                raise
            response.warnings.append(_APPROVAL_UNAVAILABLE_WARNING)
        else:
            response.approval_request_id = request.id
    return response


def _requires_human_approval(
    data: ChangePreviewCreate,
    principal: Authenticated,
) -> bool:
    return (
        principal.authentication_method == "human_session"
        and WILDCARD_PERMISSION not in principal.permissions
        and isinstance(
            data,
            (PolicyVersionCreateChangePreview, PolicyStatusChangePreview),
        )
    )


@execution_router.post("", response_model=ApprovedChangeExecutionRead)
def execute_approved_change(
    data: ApprovedChangeExecutionCreate,
    session: DatabaseSession,
    actor: AuditActor,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    principal: Authenticated,
) -> ApprovedChangeExecutionRead:
    """Execute exactly one signed preview, once, if its impact is unchanged."""
    approval_request: ChangeApprovalRequest | None = None
    if data.approval_request_id is not None:
        approval_request = session.get(
            ChangeApprovalRequest,
            data.approval_request_id,
        )
        if approval_request is None:
            raise HTTPException(status_code=404, detail="Approval request not found")
        require_approved_executor(approval_request, principal)
        approval_token = approval_request.approval_token
        change = TypeAdapter(ChangePreviewCreate).validate_python(
            approval_request.change
        )
        assert approval_token is not None
    else:
        approval_token = data.approval_token
        change = data.change
        assert approval_token is not None and change is not None
    claims = verify_change_approval(
        approval_token,
        check_expiration=False,
    )
    validate_approved_change(claims, change)
    _validate_change_scope(
        session,
        change,
        field_visibility,
        visibility,
        principal,
    )
    lock_approval_execution(session, claims.approval_id)
    existing = session.get(ApprovedChangeExecution, claims.approval_id)
    if existing is not None:
        if (
            existing.change_digest != claims.change_digest
            or existing.precondition_digest != claims.precondition_digest
            or existing.preview_digest != claims.preview_digest
        ):
            raise ChangeApprovalConflictError(
                "The approval ID is already associated with a different change",
                code="change_approval_identity_conflict",
                metadata={"approval_id": claims.approval_id},
            )
        replay = dict(existing.response)
        replay["replayed"] = True
        return ApprovedChangeExecutionRead.model_validate(replay)
    validate_approval_not_expired(claims)
    actual_precondition_digest = change_precondition_digest(
        session,
        change,
        lock=True,
    )
    if actual_precondition_digest != claims.precondition_digest:
        raise ChangeApprovalConflictError(
            "The target state has changed since approval; create and approve a "
            "new preview",
            code="change_approval_stale",
            metadata={
                "approval_id": claims.approval_id,
                "stage": "target_precondition",
                "approved_precondition_digest": claims.precondition_digest,
                "actual_precondition_digest": actual_precondition_digest,
            },
        )

    before = _current_assignments(
        session,
        visibility=visibility,
        field_visibility=field_visibility,
    )
    before_access = _current_automated_roles(session, visibility)
    context = _MutationContext()
    _apply_change(
        session,
        change,
        actor,
        context,
        visibility,
    )
    session.flush()

    comparable_after = _current_assignments(
        session,
        proposed_policy_version_ids=context.proposed_policy_version_ids,
        proposed_override_ids=context.proposed_override_ids,
        visibility=visibility,
        field_visibility=field_visibility,
        proposed_employee_ids=context.proposed_employee_ids,
    )
    comparable_changes = _assignment_changes(
        session,
        before,
        comparable_after,
        context,
    )
    comparable_access = _automated_role_changes(
        before_access,
        _current_automated_roles(session, visibility),
        context.proposed_policy_version_ids,
    )
    comparable_preview = ChangePreviewRead(
        change_type=change.type,
        valid=True,
        affected_employee_count=_affected_employee_count(comparable_changes),
        changes=comparable_changes,
        affected_user_count=len({item.user_id for item in comparable_access}),
        access_changes=comparable_access,
        conflicts=[],
        warnings=[],
    )
    actual_preview_digest = preview_digest(comparable_preview)
    if actual_preview_digest != claims.preview_digest:
        raise ChangeApprovalConflictError(
            "The assignment impact has changed since approval; create and approve "
            "a new preview",
            code="change_approval_stale",
            metadata={
                "approval_id": claims.approval_id,
                "approved_preview_digest": claims.preview_digest,
                "actual_preview_digest": actual_preview_digest,
                "current_preview": comparable_preview.model_dump(mode="json"),
            },
        )

    actual_after = _current_assignments(
        session,
        visibility=visibility,
        field_visibility=field_visibility,
        proposed_employee_ids=context.proposed_employee_ids,
    )
    actual_context = _MutationContext(
        included_employee_ids=set(context.included_employee_ids),
        resources=dict(context.resources),
    )
    actual_changes = _assignment_changes(
        session,
        before,
        actual_after,
        actual_context,
    )
    actual_access = _automated_role_changes(
        before_access,
        _current_automated_roles(session, visibility),
        set(),
    )
    executed_at = current_datetime()
    response = ApprovedChangeExecutionRead(
        approval_id=claims.approval_id,
        status="executed",
        replayed=False,
        change_type=change.type,
        executed_at=executed_at,
        executed_by=actor,
        affected_employee_count=_affected_employee_count(actual_changes),
        affected_user_count=len({item.user_id for item in actual_access}),
        changes=actual_changes,
        access_changes=actual_access,
        resources=context.resources,
    )
    session.add(
        ApprovedChangeExecution(
            approval_id=claims.approval_id,
            change_type=change.type,
            change_digest=claims.change_digest,
            precondition_digest=claims.precondition_digest,
            preview_digest=claims.preview_digest,
            executed_by=actor,
            executed_at=executed_at,
            response=response.model_dump(mode="json"),
        )
    )
    if approval_request is not None:
        mark_request_executed(
            session,
            approval_request,
            actor=actor,
        )
    session.flush()
    return response


def _apply_change(
    session: DatabaseSession,
    data: ChangePreviewCreate,
    actor: str,
    context: _MutationContext,
    visibility: EmployeeVisibility,
) -> None:
    if isinstance(data, EmployeeCreateChangePreview):
        require_employee_creation_scope(session, visibility, data.employee.manager_id)
        employee = create_employee(session, data.employee, actor)
        context.included_employee_ids.add(employee.id)
        context.proposed_employee_ids.add(employee.id)
        context.resources["employee_id"] = employee.id
        return

    if isinstance(data, EmployeeUpdateChangePreview):
        employee = visible_employee_or_404(
            session,
            visibility,
            data.employee_id,
        )
        if (
            "manager_id" in data.changes.model_fields_set
            and data.changes.manager_id is not None
            and data.changes.manager_id != employee.manager_id
        ):
            visible_employee_or_404(
                session,
                visibility,
                data.changes.manager_id,
            )
        update_employee(session, employee, data.changes, actor)
        context.included_employee_ids.add(employee.id)
        context.resources["employee_id"] = employee.id
        return

    if isinstance(data, PolicyVersionCreateChangePreview):
        policy = session.get(Policy, data.policy_id)
        assert policy is not None
        version = create_policy_version_from_input(
            session,
            policy,
            data.version,
            actor,
        )
        context.proposed_policy_version_ids.add(version.id)
        context.resources["policy_id"] = policy.id
        context.resources["policy_version_id"] = version.id
        refresh_employees_affected_by_policy(session, policy)
        return

    if isinstance(data, PolicyStatusChangePreview):
        policy = session.get(Policy, data.policy_id)
        assert policy is not None
        before = snapshot_entity(policy)
        policy.status = data.status
        session.flush()
        after = snapshot_entity(policy)
        if before != after:
            record_audit_log(
                session,
                actor=actor,
                entity_type="Policy",
                entity_id=policy.id,
                action="archived" if data.status == "archived" else "changed",
                before=before,
                after=after,
            )
            sync_policy_version_schedules(session, policy)
            sync_all_employee_tenure_schedules(session)
            refresh_employees_affected_by_policy(session, policy)
        context.resources["policy_id"] = policy.id
        return

    if isinstance(data, GroupMembershipChangePreview):
        visible_employee_or_404(session, visibility, data.employee_id)
        if data.action == "add":
            add_employee_to_group(
                session,
                data.group_id,
                data.employee_id,
                actor,
            )
        else:
            remove_employee_from_group(
                session,
                data.group_id,
                data.employee_id,
                actor,
            )
        context.included_employee_ids.add(data.employee_id)
        context.resources["employee_id"] = data.employee_id
        context.resources["group_id"] = data.group_id
        return

    if isinstance(data, EmployeeOverrideChangePreview):
        visible_employee_or_404(session, visibility, data.employee_id)
        context.included_employee_ids.add(data.employee_id)
        if data.action == "create":
            assignment_field_definition_id = data.assignment_field_definition_id
            value = data.value
            assert assignment_field_definition_id is not None
            assert value is not None
            override = create_employee_override(
                session,
                data.employee_id,
                assignment_field_definition_id,
                value,
                actor,
            )
            context.proposed_override_ids.add(override.id)
            context.resources["override_id"] = override.id
        elif data.action == "update":
            override_id = data.override_id
            assert override_id is not None
            override = update_employee_override(
                session,
                data.employee_id,
                override_id,
                data.assignment_field_definition_id,
                data.value,
                actor,
            )
            if override.id != override_id:
                context.proposed_override_ids.add(override.id)
            context.resources["override_id"] = override.id
        else:
            override_id = data.override_id
            assert override_id is not None
            delete_employee_override(
                session,
                data.employee_id,
                override_id,
                actor,
            )
            context.resources["override_id"] = override_id
        context.resources["employee_id"] = data.employee_id
        return

    raise ValueError(f"Unsupported change preview type: {data.type}")


def _validate_change_scope(
    session: DatabaseSession,
    data: ChangePreviewCreate,
    field_visibility: AssignmentFieldVisibility,
    employee_visibility: EmployeeVisibility,
    principal: Authenticated,
) -> None:
    if isinstance(data, PolicyVersionCreateChangePreview):
        require_visible_policy(session, field_visibility, data.policy_id)
        policy = session.get(Policy, data.policy_id)
        assert policy is not None
        require_policy_version_create(principal, policy)
        if data.version.automated_role_ids and not employee_visibility.unrestricted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Automated access changes require organization-wide employee "
                    "visibility so the complete impact can be reviewed"
                ),
            )
        validate_assignment_field_ids(
            session,
            field_visibility,
            (
                value.assignment_field_definition_id
                for value in data.version.values
            ),
        )
    elif isinstance(data, PolicyStatusChangePreview):
        require_visible_policy(session, field_visibility, data.policy_id)
        policy = session.get(Policy, data.policy_id)
        assert policy is not None
        if (
            any(version.role_grants for version in policy.versions)
            and not employee_visibility.unrestricted
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Automated access changes require organization-wide employee "
                    "visibility so the complete impact can be reviewed"
                ),
            )
        require_policy_permission(
            principal,
            (
                "policies:activate"
                if data.status == "active"
                else "policies:archive"
                if data.status == "archived"
                else "policies:update"
            ),
        )
    elif isinstance(data, EmployeeOverrideChangePreview):
        if data.override_id is not None:
            _require_visible_override(
                session,
                field_visibility,
                data.employee_id,
                data.override_id,
            )
        if data.assignment_field_definition_id is not None:
            visible_assignment_field_or_404(
                session,
                field_visibility,
                data.assignment_field_definition_id,
            )


def _preview_conflict_issue(
    exc: Exception,
    context: _MutationContext,
) -> dict[str, Any]:
    issue = conflict_issue(exc).model_dump(mode="json")
    candidates = issue["metadata"].get("candidates", [])
    for candidate in candidates:
        policy_version_id = candidate.get("policy_version_id")
        if policy_version_id in context.proposed_policy_version_ids:
            candidate["policy_version_id"] = None
            candidate["source_is_proposed"] = True
    return issue


def _affected_employee_count(
    changes: list[EmployeeAssignmentPreviewChangeRead],
) -> int:
    return sum(bool(item.added or item.removed or item.changed) for item in changes)


def _current_automated_roles(
    session: DatabaseSession,
    visibility: EmployeeVisibility,
) -> dict[tuple[int, int, int], tuple[int, str, str]]:
    statement = (
        select(
            AutomatedUserRole.user_id,
            AutomatedUserRole.role_id,
            AutomatedUserRole.source_policy_version_id,
            Employee.id,
            Employee.name,
            Role.name,
        )
        .join(User, User.id == AutomatedUserRole.user_id)
        .join(Employee, Employee.id == User.employee_id)
        .join(Role, Role.id == AutomatedUserRole.role_id)
    )
    statement = visibility.apply(statement, Employee.id)
    return {
        (user_id, role_id, source_policy_version_id): (
            employee_id,
            employee_name,
            role_name,
        )
        for (
            user_id,
            role_id,
            source_policy_version_id,
            employee_id,
            employee_name,
            role_name,
        ) in session.execute(statement)
    }


def _automated_role_changes(
    before: dict[tuple[int, int, int], tuple[int, str, str]],
    after: dict[tuple[int, int, int], tuple[int, str, str]],
    proposed_policy_version_ids: set[int],
) -> list[AutomatedRolePreviewChangeRead]:
    changes: list[AutomatedRolePreviewChangeRead] = []
    for action, keys, state in (
        ("revoke", sorted(before.keys() - after.keys()), before),
        ("grant", sorted(after.keys() - before.keys()), after),
    ):
        for user_id, role_id, source_policy_version_id in keys:
            employee_id, employee_name, role_name = state[
                (user_id, role_id, source_policy_version_id)
            ]
            source_is_proposed = (
                source_policy_version_id in proposed_policy_version_ids
            )
            changes.append(
                AutomatedRolePreviewChangeRead(
                    user_id=user_id,
                    employee_id=employee_id,
                    employee_name=employee_name,
                    role_id=role_id,
                    role_name=role_name,
                    action=action,
                    source_policy_version_id=(
                        None if source_is_proposed else source_policy_version_id
                    ),
                    source_is_proposed=source_is_proposed,
                )
            )
    return changes


def _current_assignments(
    session: DatabaseSession,
    *,
    proposed_policy_version_ids: set[int] | None = None,
    proposed_override_ids: set[int] | None = None,
    visibility: EmployeeVisibility,
    field_visibility: AssignmentFieldVisibility,
    proposed_employee_ids: set[int] | None = None,
) -> dict[int, list[AssignmentPreviewRead]]:
    proposed_policy_version_ids = proposed_policy_version_ids or set()
    proposed_override_ids = proposed_override_ids or set()
    statement = (
        select(EmployeeAssignment)
        .where(EmployeeAssignment.effective_until.is_(None))
        .options(joinedload(EmployeeAssignment.assignment_field_definition))
        .order_by(
            EmployeeAssignment.employee_id,
            EmployeeAssignment.assignment_field_definition_id,
            EmployeeAssignment.value,
            EmployeeAssignment.id,
        )
    )
    if not visibility.unrestricted:
        visible_ids = set(visibility.employee_ids)
        visible_ids.update(proposed_employee_ids or set())
        statement = statement.where(EmployeeAssignment.employee_id.in_(visible_ids))
    statement = field_visibility.apply(
        statement,
        EmployeeAssignment.assignment_field_definition_id,
    )
    assignments = list(
        session.scalars(
            statement
        )
    )
    result: dict[int, list[AssignmentPreviewRead]] = {}
    for assignment in assignments:
        if assignment.source_policy_version_id is not None:
            source_type = "policy_version"
            source_id = assignment.source_policy_version_id
            source_is_proposed = source_id in proposed_policy_version_ids
        else:
            source_type = "override"
            source_id = assignment.source_override_id
            source_is_proposed = source_id in proposed_override_ids
        result.setdefault(assignment.employee_id, []).append(
            AssignmentPreviewRead(
                assignment_field_definition_id=(
                    assignment.assignment_field_definition_id
                ),
                assignment_field_name=(
                    assignment.assignment_field_definition.name
                ),
                value=assignment.value,
                source_type=source_type,
                source_id=None if source_is_proposed else source_id,
                source_is_proposed=source_is_proposed,
                explanation=_sanitize_explanation(
                    assignment.explanation or {},
                    proposed_policy_version_ids,
                    proposed_override_ids,
                ),
            )
        )
    return result


def _require_visible_override(
    session: DatabaseSession,
    visibility: AssignmentFieldVisibility,
    employee_id: int,
    override_id: int,
) -> None:
    override = session.scalar(
        visibility.apply(
            select(EmployeeOverride).where(
                EmployeeOverride.id == override_id,
                EmployeeOverride.employee_id == employee_id,
                EmployeeOverride.retired_at.is_(None),
            ),
            EmployeeOverride.assignment_field_definition_id,
        )
    )
    if override is None:
        raise HTTPException(
            status_code=404,
            detail=f"Override {override_id} not found for employee {employee_id}",
        )


def _assignment_changes(
    session: DatabaseSession,
    before: dict[int, list[AssignmentPreviewRead]],
    after: dict[int, list[AssignmentPreviewRead]],
    context: _MutationContext,
) -> list[EmployeeAssignmentPreviewChangeRead]:
    employee_ids = sorted(before.keys() | after.keys() | context.included_employee_ids)
    names = {
        employee.id: employee.name
        for employee in session.scalars(
            select(Employee).where(Employee.id.in_(employee_ids))
        )
    }
    changes: list[EmployeeAssignmentPreviewChangeRead] = []
    for employee_id in employee_ids:
        before_items = before.get(employee_id, [])
        after_items = after.get(employee_id, [])
        added = _list_difference(after_items, before_items)
        removed = _list_difference(before_items, after_items)
        changed = _changed_fields(before_items, after_items)
        if not (added or removed or changed) and employee_id not in context.included_employee_ids:
            continue
        changes.append(
            EmployeeAssignmentPreviewChangeRead(
                employee_id=(
                    None
                    if employee_id in context.proposed_employee_ids
                    else employee_id
                ),
                employee_name=names[employee_id],
                before=before_items,
                after=after_items,
                added=added,
                removed=removed,
                changed=changed,
            )
        )
    return changes


def _list_difference(
    left: list[AssignmentPreviewRead],
    right: list[AssignmentPreviewRead],
) -> list[AssignmentPreviewRead]:
    right_keys = {_assignment_key(item) for item in right}
    return [item for item in left if _assignment_key(item) not in right_keys]


def _changed_fields(
    before: list[AssignmentPreviewRead],
    after: list[AssignmentPreviewRead],
) -> list[AssignmentFieldPreviewChangeRead]:
    before_by_field = _by_field(before)
    after_by_field = _by_field(after)
    changed = []
    for field_id in sorted(before_by_field.keys() | after_by_field.keys()):
        before_items = before_by_field.get(field_id, [])
        after_items = after_by_field.get(field_id, [])
        if [_assignment_key(item) for item in before_items] == [
            _assignment_key(item) for item in after_items
        ]:
            continue
        items = after_items or before_items
        changed.append(
            AssignmentFieldPreviewChangeRead(
                assignment_field_definition_id=field_id,
                assignment_field_name=items[0].assignment_field_name,
                before=before_items,
                after=after_items,
            )
        )
    return changed


def _by_field(
    assignments: list[AssignmentPreviewRead],
) -> dict[int, list[AssignmentPreviewRead]]:
    result: dict[int, list[AssignmentPreviewRead]] = {}
    for assignment in assignments:
        result.setdefault(assignment.assignment_field_definition_id, []).append(
            assignment
        )
    return result


def _assignment_key(assignment: AssignmentPreviewRead) -> str:
    return json.dumps(
        assignment.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


def _sanitize_explanation(
    value: Any,
    proposed_policy_version_ids: set[int],
    proposed_override_ids: set[int],
    *,
    parent_key: str | None = None,
) -> Any:
    if isinstance(value, list):
        return [
            _sanitize_explanation(
                item,
                proposed_policy_version_ids,
                proposed_override_ids,
                parent_key=parent_key,
            )
            for item in value
        ]
    if not isinstance(value, dict):
        return value

    result: dict[str, Any] = {}
    for key, item in value.items():
        proposed = (
            key in {"policy_version_id", "source_policy_version_id"}
            and item in proposed_policy_version_ids
        ) or (
            key in {"override_id", "source_override_id"}
            and item in proposed_override_ids
        ) or (
            key == "id"
            and parent_key == "policy_version"
            and item in proposed_policy_version_ids
        ) or (
            key == "id"
            and parent_key == "override"
            and item in proposed_override_ids
        )
        result[key] = (
            None
            if proposed
            else _sanitize_explanation(
                item,
                proposed_policy_version_ids,
                proposed_override_ids,
                parent_key=key,
            )
        )
        if proposed:
            result["source_is_proposed"] = True
    return result
