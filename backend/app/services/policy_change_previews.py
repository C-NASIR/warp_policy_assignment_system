from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.error_contract import conflict_issue
from app.models import (
    AssignmentFieldDefinition,
    Employee,
    EmployeeAssignment,
    Policy,
    PolicyVersion,
)
from app.schemas import (
    PolicyAssignmentPreviewRead,
    PolicyCreateChangePreview,
    PolicyPreviewAssignmentRead,
    PolicyPreviewEmployeeRead,
    PolicyVersionCreateChangePreview,
)
from app.services.assignment_field_visibility import AssignmentFieldVisibility
from app.services.audit import record_audit_log, snapshot_entity
from app.services.employee_visibility import EmployeeVisibility
from app.services.org_chart import EmployeeHierarchyConflictError
from app.services.policy_authoring import create_policy_version_from_input
from app.services.policy_engine import PolicyConflictError
from app.services.policy_reconciliation import refresh_employees_affected_by_policy
from app.services.policy_versions import (
    EffectivePolicyVersionConflictError,
    PolicyVersionOverlapError,
)

PolicyChangePreview = PolicyCreateChangePreview | PolicyVersionCreateChangePreview
AssignmentKey = tuple[int, str, int | None, int | None, str]


@dataclass(frozen=True)
class AppliedPolicyChange:
    policy: Policy
    version: PolicyVersion


def preview_policy(
    session: Session,
    data: PolicyChangePreview,
    actor: str,
    visibility: EmployeeVisibility,
    field_visibility: AssignmentFieldVisibility,
) -> PolicyAssignmentPreviewRead:
    """Simulate a policy mutation and return its frontend-facing impact summary."""
    savepoint = session.begin_nested()
    try:
        before = _current_assignment_keys(session, visibility, field_visibility)
        try:
            apply_policy_change(session, data, actor)
            session.flush()
            after = _current_assignment_keys(session, visibility, field_visibility)
            affected_employee_ids = sorted(
                employee_id
                for employee_id in before.keys() | after.keys()
                if before.get(employee_id, []) != after.get(employee_id, [])
            )
            conflict_message = None
        except (
            EffectivePolicyVersionConflictError,
            EmployeeHierarchyConflictError,
            PolicyConflictError,
            PolicyVersionOverlapError,
        ) as exc:
            affected_employee_ids = []
            conflict_message = conflict_issue(exc).message

        response = _policy_assignment_preview(
            session,
            data,
            affected_employee_ids,
            conflict_message,
        )
    finally:
        if savepoint.is_active:
            savepoint.rollback()
        session.expire_all()

    return response


def apply_policy_change(
    session: Session,
    data: PolicyChangePreview,
    actor: str,
) -> AppliedPolicyChange:
    """Apply a policy change inside a preview simulation."""
    if isinstance(data, PolicyCreateChangePreview):
        policy = Policy(
            name=data.policy.name,
            status=data.policy.status,
            created_by=actor,
        )
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
        version_data = data.policy
    else:
        policy = session.get(Policy, data.policy_id)
        assert policy is not None
        version_data = data.version

    version = create_policy_version_from_input(
        session,
        policy,
        version_data,
        actor,
    )
    refresh_employees_affected_by_policy(session, policy)
    return AppliedPolicyChange(policy=policy, version=version)


def _policy_assignment_preview(
    session: Session,
    data: PolicyChangePreview,
    affected_employee_ids: list[int],
    conflict_message: str | None,
) -> PolicyAssignmentPreviewRead:
    employees = {
        employee.id: employee
        for employee in session.scalars(
            select(Employee).where(Employee.id.in_(affected_employee_ids))
        )
    }
    version = (
        data.policy if isinstance(data, PolicyCreateChangePreview) else data.version
    )
    field_ids = {value.assignment_field_definition_id for value in version.values}
    field_names = {
        field.id: field.name
        for field in session.scalars(
            select(AssignmentFieldDefinition).where(
                AssignmentFieldDefinition.id.in_(field_ids)
            )
        )
    }

    return PolicyAssignmentPreviewRead(
        type=data.type,
        affected_employees=[
            PolicyPreviewEmployeeRead(
                employee_id=employee_id,
                employee_name=employees[employee_id].name,
                department=employees[employee_id].department,
            )
            for employee_id in affected_employee_ids
        ],
        assignments_per_match=[
            PolicyPreviewAssignmentRead(
                assignment_field_definition_id=value.assignment_field_definition_id,
                assignment_field_name=field_names[value.assignment_field_definition_id],
                value=value.value,
            )
            for value in version.values
        ],
        conflict_message=conflict_message,
    )


def _current_assignment_keys(
    session: Session,
    visibility: EmployeeVisibility,
    field_visibility: AssignmentFieldVisibility,
) -> dict[int, list[AssignmentKey]]:
    statement = (
        select(EmployeeAssignment)
        .where(EmployeeAssignment.effective_until.is_(None))
        .order_by(
            EmployeeAssignment.employee_id,
            EmployeeAssignment.assignment_field_definition_id,
            EmployeeAssignment.value,
            EmployeeAssignment.id,
        )
    )
    if not visibility.unrestricted:
        statement = statement.where(
            EmployeeAssignment.employee_id.in_(visibility.employee_ids)
        )
    statement = field_visibility.apply(
        statement,
        EmployeeAssignment.assignment_field_definition_id,
    )
    result: dict[int, list[AssignmentKey]] = {}
    for assignment in session.scalars(statement):
        result.setdefault(assignment.employee_id, []).append(
            (
                assignment.assignment_field_definition_id,
                assignment.value,
                assignment.source_policy_version_id,
                assignment.source_override_id,
                json.dumps(
                    assignment.explanation or {},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        )
    return result
