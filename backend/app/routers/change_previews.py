from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.dependencies import (
    AssignmentFieldScope,
    AuditActor,
    Authenticated,
    DatabaseSession,
    EmployeeScope,
)
from app.error_contract import conflict_issue
from app.models import (
    Employee,
    EmployeeAssignment,
    EmployeeOverride,
    Policy,
)
from app.schemas import (
    AssignmentFieldPreviewChangeRead,
    AssignmentPreviewRead,
    ChangePreviewCreate,
    ChangePreviewRead,
    ChangePreviewResponse,
    EmployeeAssignmentPreviewChangeRead,
    EmployeeCreateChangePreview,
    EmployeeOverrideChangePreview,
    EmployeeUpdateChangePreview,
    GroupMembershipChangePreview,
    NonPolicyChangePreviewRead,
    PolicyCreateChangePreview,
    PolicyStatusChangePreview,
    PolicyVersionCreateChangePreview,
)
from app.services.assignment_field_visibility import (
    AssignmentFieldVisibility,
    require_visible_policy,
    validate_assignment_field_ids,
    visible_assignment_field_or_404,
)
from app.services.audit import record_audit_log, snapshot_entity
from app.services.employee_change_previews import (
    apply_employee_change,
    preview_employee,
)
from app.services.employee_overrides import (
    EmployeeOverrideConflictError,
    create_employee_override,
    delete_employee_override,
    update_employee_override,
)
from app.services.employee_visibility import (
    EmployeeVisibility,
    visible_employee_or_404,
)
from app.services.groups import add_employee_to_group, remove_employee_from_group
from app.services.org_chart import EmployeeHierarchyConflictError
from app.services.policy_access import (
    require_policy_permission,
    require_policy_version_create,
)
from app.services.policy_change_previews import apply_policy_change, preview_policy
from app.services.policy_engine import PolicyConflictError
from app.services.policy_reconciliation import refresh_employees_affected_by_policy
from app.services.policy_versions import (
    EffectivePolicyVersionConflictError,
    PolicyVersionOverlapError,
)
from app.services.scheduled_reconciliations import sync_policy_version_schedules
from app.services.tenure_scheduling import sync_all_employee_tenure_schedules

router = APIRouter(prefix="/change-previews", tags=["change previews"])


@dataclass
class _MutationContext:
    included_employee_ids: set[int] = field(default_factory=set)
    proposed_employee_ids: set[int] = field(default_factory=set)
    proposed_policy_version_ids: set[int] = field(default_factory=set)
    proposed_policy_ids: set[int] = field(default_factory=set)
    proposed_condition_clause_ids: set[int] = field(default_factory=set)
    proposed_override_ids: set[int] = field(default_factory=set)
    resources: dict[str, int] = field(default_factory=dict)


@router.post("", response_model=ChangePreviewResponse)
def preview(
    data: ChangePreviewCreate,
    session: DatabaseSession,
    actor: AuditActor,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
    principal: Authenticated,
) -> ChangePreviewResponse:
    """Simulate one supported mutation and roll back every resulting write."""
    _validate_change_scope(
        session,
        data,
        field_visibility,
        visibility,
        principal,
    )
    if isinstance(data, (EmployeeCreateChangePreview, EmployeeUpdateChangePreview)):
        return preview_employee(
            session,
            data,
            actor,
            visibility,
            field_visibility,
        )

    if isinstance(data, (PolicyCreateChangePreview, PolicyVersionCreateChangePreview)):
        return preview_policy(
            session,
            data,
            actor,
            visibility,
            field_visibility,
        )

    savepoint = session.begin_nested()
    try:
        before = _current_assignments(
            session,
            visibility=visibility,
            field_visibility=field_visibility,
        )
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
                proposed_policy_ids=context.proposed_policy_ids,
                proposed_condition_clause_ids=context.proposed_condition_clause_ids,
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
            response = ChangePreviewRead(
                type=data.type,
                valid=True,
                affected_employee_count=sum(
                    bool(item.added or item.removed or item.changed) for item in changes
                ),
                changes=changes,
                conflicts=[],
                warnings=[],
            )
        except (
            EffectivePolicyVersionConflictError,
            EmployeeHierarchyConflictError,
            EmployeeOverrideConflictError,
            PolicyConflictError,
            PolicyVersionOverlapError,
        ) as exc:
            response = ChangePreviewRead(
                type=data.type,
                valid=False,
                affected_employee_count=0,
                changes=[],
                conflicts=[_preview_conflict_issue(exc, context)],
                warnings=[],
            )
    finally:
        if savepoint.is_active:
            savepoint.rollback()
        session.expire_all()
    return NonPolicyChangePreviewRead.model_validate(response.model_dump())


def _apply_change(
    session: DatabaseSession,
    data: ChangePreviewCreate,
    actor: str,
    context: _MutationContext,
    visibility: EmployeeVisibility,
) -> None:
    if isinstance(data, (EmployeeCreateChangePreview, EmployeeUpdateChangePreview)):
        employee = apply_employee_change(session, data, actor, visibility)
        context.included_employee_ids.add(employee.id)
        if isinstance(data, EmployeeCreateChangePreview):
            context.proposed_employee_ids.add(employee.id)
        context.resources["employee_id"] = employee.id
        return

    if isinstance(data, (PolicyCreateChangePreview, PolicyVersionCreateChangePreview)):
        applied = apply_policy_change(session, data, actor)
        context.proposed_policy_version_ids.add(applied.version.id)
        if isinstance(data, PolicyCreateChangePreview):
            context.proposed_policy_ids.add(applied.policy.id)
        context.proposed_condition_clause_ids.update(
            clause.id for clause in applied.version.compiled_clauses
        )
        context.resources["policy_id"] = applied.policy.id
        context.resources["policy_version_id"] = applied.version.id
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
            refresh_employees_affected_by_policy(session, policy, actor=actor)
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
    if isinstance(data, PolicyCreateChangePreview):
        require_policy_permission(principal, "policies:create")
        if data.policy.status == "active":
            require_policy_permission(principal, "policies:activate")
        elif data.policy.status == "archived":
            require_policy_permission(principal, "policies:archive")
        validate_assignment_field_ids(
            session,
            field_visibility,
            (value.assignment_field_definition_id for value in data.policy.values),
        )
    elif isinstance(data, PolicyVersionCreateChangePreview):
        require_visible_policy(session, field_visibility, data.policy_id)
        policy = session.get(Policy, data.policy_id)
        assert policy is not None
        require_policy_version_create(principal, policy)
        validate_assignment_field_ids(
            session,
            field_visibility,
            (value.assignment_field_definition_id for value in data.version.values),
        )
    elif isinstance(data, PolicyStatusChangePreview):
        require_visible_policy(session, field_visibility, data.policy_id)
        policy = session.get(Policy, data.policy_id)
        assert policy is not None
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


def _current_assignments(
    session: DatabaseSession,
    *,
    proposed_policy_version_ids: set[int] | None = None,
    proposed_policy_ids: set[int] | None = None,
    proposed_condition_clause_ids: set[int] | None = None,
    proposed_override_ids: set[int] | None = None,
    visibility: EmployeeVisibility,
    field_visibility: AssignmentFieldVisibility,
    proposed_employee_ids: set[int] | None = None,
) -> dict[int, list[AssignmentPreviewRead]]:
    proposed_policy_version_ids = proposed_policy_version_ids or set()
    proposed_policy_ids = proposed_policy_ids or set()
    proposed_condition_clause_ids = proposed_condition_clause_ids or set()
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
    assignments = list(session.scalars(statement))
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
                assignment_field_name=(assignment.assignment_field_definition.name),
                value=assignment.value,
                source_type=source_type,
                source_id=None if source_is_proposed else source_id,
                source_is_proposed=source_is_proposed,
                explanation=_sanitize_explanation(
                    assignment.explanation or {},
                    proposed_policy_version_ids,
                    proposed_policy_ids,
                    proposed_condition_clause_ids,
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
        if (
            not (added or removed or changed)
            and employee_id not in context.included_employee_ids
        ):
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
    proposed_policy_ids: set[int],
    proposed_condition_clause_ids: set[int],
    proposed_override_ids: set[int],
    *,
    parent_key: str | None = None,
) -> Any:
    if isinstance(value, list):
        return [
            _sanitize_explanation(
                item,
                proposed_policy_version_ids,
                proposed_policy_ids,
                proposed_condition_clause_ids,
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
            (
                key in {"policy_version_id", "source_policy_version_id"}
                and item in proposed_policy_version_ids
            )
            or (key == "policy_id" and item in proposed_policy_ids)
            or (key == "clause_id" and item in proposed_condition_clause_ids)
            or (
                key in {"override_id", "source_override_id"}
                and item in proposed_override_ids
            )
            or (key == "id" and parent_key == "policy" and item in proposed_policy_ids)
            or (
                key == "id"
                and parent_key == "policy_version"
                and item in proposed_policy_version_ids
            )
            or (
                key == "id"
                and parent_key == "override"
                and item in proposed_override_ids
            )
        )
        result[key] = (
            None
            if proposed
            else _sanitize_explanation(
                item,
                proposed_policy_version_ids,
                proposed_policy_ids,
                proposed_condition_clause_ids,
                proposed_override_ids,
                parent_key=key,
            )
        )
        if proposed:
            result["source_is_proposed"] = True
    return result
