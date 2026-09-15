from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.error_contract import conflict_issue
from app.models import Employee, EmployeeAssignment
from app.schemas import (
    AssignmentPreviewRead,
    EmployeeAssignmentPreviewRead,
    EmployeeCreateChangePreview,
    EmployeeUpdateChangePreview,
)
from app.services.assignment_field_visibility import AssignmentFieldVisibility
from app.services.employee_visibility import (
    EmployeeVisibility,
    require_employee_creation_scope,
    visible_employee_or_404,
)
from app.services.employees import create_employee, update_employee
from app.services.org_chart import EmployeeHierarchyConflictError
from app.services.policy_engine import PolicyConflictError

EmployeeChangePreview = EmployeeCreateChangePreview | EmployeeUpdateChangePreview


def preview_employee(
    session: Session,
    data: EmployeeChangePreview,
    actor: str,
    visibility: EmployeeVisibility,
    field_visibility: AssignmentFieldVisibility,
) -> EmployeeAssignmentPreviewRead:
    """Simulate an employee mutation and return its assignment snapshots."""
    savepoint = session.begin_nested()
    before_assignments: list[AssignmentPreviewRead] = []
    try:
        try:
            if isinstance(data, EmployeeCreateChangePreview):
                employee = _create_employee_change(session, data, actor, visibility)
            else:
                employee = visible_employee_or_404(
                    session,
                    visibility,
                    data.employee_id,
                )
                before_assignments = _employee_assignments(
                    session,
                    employee.id,
                    field_visibility,
                )
                _update_employee_change(session, data, employee, actor, visibility)

            session.flush()
            after_assignments = _employee_assignments(
                session,
                employee.id,
                field_visibility,
            )
            response = employee_assignment_preview(
                data,
                before_assignments,
                after_assignments,
            )
        except (EmployeeHierarchyConflictError, PolicyConflictError) as exc:
            response = EmployeeAssignmentPreviewRead(
                type=data.type,
                valid=False,
                before_assignments=before_assignments,
                after_assignments=before_assignments,
                conflicts=[conflict_issue(exc).model_dump(mode="json")],
                warnings=[],
            )
    finally:
        if savepoint.is_active:
            savepoint.rollback()
        session.expire_all()

    return response


def employee_assignment_preview(
    data: EmployeeChangePreview,
    before_assignments: list[AssignmentPreviewRead],
    after_assignments: list[AssignmentPreviewRead],
) -> EmployeeAssignmentPreviewRead:
    """Build the stable response returned by employee change previews."""
    return EmployeeAssignmentPreviewRead(
        type=data.type,
        valid=True,
        before_assignments=before_assignments,
        after_assignments=after_assignments,
        conflicts=[],
        warnings=[],
    )


def apply_employee_change(
    session: Session,
    data: EmployeeChangePreview,
    actor: str,
    visibility: EmployeeVisibility,
) -> Employee:
    """Apply an employee change inside a preview simulation."""
    if isinstance(data, EmployeeCreateChangePreview):
        return _create_employee_change(session, data, actor, visibility)
    employee = visible_employee_or_404(session, visibility, data.employee_id)
    return _update_employee_change(session, data, employee, actor, visibility)


def _employee_assignments(
    session: Session,
    employee_id: int,
    field_visibility: AssignmentFieldVisibility,
) -> list[AssignmentPreviewRead]:
    statement = (
        select(EmployeeAssignment)
        .where(
            EmployeeAssignment.employee_id == employee_id,
            EmployeeAssignment.effective_until.is_(None),
        )
        .options(joinedload(EmployeeAssignment.assignment_field_definition))
        .order_by(
            EmployeeAssignment.assignment_field_definition_id,
            EmployeeAssignment.value,
            EmployeeAssignment.id,
        )
    )
    assignments = session.scalars(
        field_visibility.apply(
            statement,
            EmployeeAssignment.assignment_field_definition_id,
        )
    )
    return [
        AssignmentPreviewRead(
            assignment_field_definition_id=(assignment.assignment_field_definition_id),
            assignment_field_name=assignment.assignment_field_definition.name,
            value=assignment.value,
            source_type=(
                "policy_version"
                if assignment.source_policy_version_id is not None
                else "override"
            ),
            source_id=(
                assignment.source_policy_version_id
                if assignment.source_policy_version_id is not None
                else assignment.source_override_id
            ),
            source_is_proposed=False,
            explanation=assignment.explanation or {},
        )
        for assignment in assignments
    ]


def _create_employee_change(
    session: Session,
    data: EmployeeCreateChangePreview,
    actor: str,
    visibility: EmployeeVisibility,
) -> Employee:
    require_employee_creation_scope(session, visibility, data.employee.manager_id)
    return create_employee(session, data.employee, actor)


def _update_employee_change(
    session: Session,
    data: EmployeeUpdateChangePreview,
    employee: Employee,
    actor: str,
    visibility: EmployeeVisibility,
) -> Employee:
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
    return update_employee(session, employee, data.changes, actor)
