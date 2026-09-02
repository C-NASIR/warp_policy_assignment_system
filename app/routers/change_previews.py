from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.dependencies import AuditActor, DatabaseSession
from app.error_contract import conflict_issue
from app.models import Employee, EmployeeAssignment, Policy
from app.schemas import (
    AssignmentFieldPreviewChangeRead,
    AssignmentPreviewRead,
    ChangePreviewCreate,
    ChangePreviewRead,
    EmployeeAssignmentPreviewChangeRead,
    EmployeeCreateChangePreview,
    EmployeeOverrideChangePreview,
    EmployeeUpdateChangePreview,
    GroupMembershipChangePreview,
    PolicyVersionCreateChangePreview,
)
from app.services.employee_overrides import (
    EmployeeOverrideConflictError,
    create_employee_override,
    delete_employee_override,
    update_employee_override,
)
from app.services.employees import create_employee, update_employee
from app.services.groups import add_employee_to_group, remove_employee_from_group
from app.services.org_chart import EmployeeHierarchyConflictError
from app.services.policy_authoring import create_policy_version_from_input
from app.services.policy_engine import PolicyConflictError
from app.services.policy_reconciliation import refresh_employees_affected_by_policy
from app.services.policy_versions import (
    EffectivePolicyVersionConflictError,
    PolicyVersionOverlapError,
)

router = APIRouter(prefix="/change-previews", tags=["change previews"])


@dataclass
class _MutationContext:
    included_employee_ids: set[int] = field(default_factory=set)
    proposed_employee_ids: set[int] = field(default_factory=set)
    proposed_policy_version_ids: set[int] = field(default_factory=set)
    proposed_override_ids: set[int] = field(default_factory=set)


@router.post("", response_model=ChangePreviewRead)
def preview(
    data: ChangePreviewCreate,
    session: DatabaseSession,
    actor: AuditActor,
) -> ChangePreviewRead:
    """Simulate one supported mutation and roll back every resulting write."""
    savepoint = session.begin_nested()
    try:
        before = _current_assignments(session)
        context = _MutationContext()
        try:
            _apply_change(session, data, actor, context)
            session.flush()
            after = _current_assignments(
                session,
                proposed_policy_version_ids=context.proposed_policy_version_ids,
                proposed_override_ids=context.proposed_override_ids,
            )
            changes = _assignment_changes(
                session,
                before,
                after,
                context,
            )
            response = ChangePreviewRead(
                change_type=data.type,
                valid=True,
                affected_employee_count=sum(
                    bool(item.added or item.removed or item.changed)
                    for item in changes
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
    return response


def _apply_change(
    session: DatabaseSession,
    data: ChangePreviewCreate,
    actor: str,
    context: _MutationContext,
) -> None:
    if isinstance(data, EmployeeCreateChangePreview):
        employee = create_employee(session, data.employee, actor)
        context.included_employee_ids.add(employee.id)
        context.proposed_employee_ids.add(employee.id)
        return

    if isinstance(data, EmployeeUpdateChangePreview):
        employee = _employee_or_404(session, data.employee_id)
        update_employee(session, employee, data.changes, actor)
        context.included_employee_ids.add(employee.id)
        return

    if isinstance(data, PolicyVersionCreateChangePreview):
        policy = session.get(Policy, data.policy_id)
        if policy is None:
            raise HTTPException(
                status_code=404,
                detail=f"Policy {data.policy_id} not found",
            )
        version = create_policy_version_from_input(
            session,
            policy,
            data.version,
            actor,
        )
        context.proposed_policy_version_ids.add(version.id)
        refresh_employees_affected_by_policy(session, policy)
        return

    if isinstance(data, GroupMembershipChangePreview):
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
        return

    if isinstance(data, EmployeeOverrideChangePreview):
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
        else:
            override_id = data.override_id
            assert override_id is not None
            delete_employee_override(
                session,
                data.employee_id,
                override_id,
                actor,
            )
        return

    raise ValueError(f"Unsupported change preview type: {data.type}")


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


def _employee_or_404(session: DatabaseSession, employee_id: int) -> Employee:
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(
            status_code=404,
            detail=f"Employee {employee_id} not found",
        )
    return employee


def _current_assignments(
    session: DatabaseSession,
    *,
    proposed_policy_version_ids: set[int] | None = None,
    proposed_override_ids: set[int] | None = None,
) -> dict[int, list[AssignmentPreviewRead]]:
    proposed_policy_version_ids = proposed_policy_version_ids or set()
    proposed_override_ids = proposed_override_ids or set()
    assignments = list(
        session.scalars(
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
