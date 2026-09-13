from collections.abc import Iterator

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssignmentFieldDefinition,
    Condition,
    ConditionFieldDefinition,
    ConditionGroup,
    ConditionGroupCondition,
    Employee,
    Policy,
    PolicyFieldValue,
    PolicyVersion,
)
from app.schemas import ConditionGroupCreate, PolicyVersionCreate
from app.services.assignment_values import (
    AssignmentValueError,
    normalize_assignment_value,
)
from app.services.condition_fields import (
    ConditionFieldError,
    get_condition_field_definitions,
)
from app.services.policy_compiler import (
    PolicyCompilationError,
    compile_policy_version_clauses,
)
from app.services.policy_versions import create_policy_version
from app.services.scheduled_reconciliations import sync_policy_version_schedules
from app.services.tenure_scheduling import sync_all_employee_tenure_schedules


def create_policy_version_from_input(
    session: Session,
    policy: Policy,
    data: PolicyVersionCreate,
    actor: str,
) -> PolicyVersion:
    """Validate and persist the canonical representation of a policy version."""
    assignment_definitions = _validate_assignment_field_definitions(
        session, data.values
    )
    for item in data.values:
        try:
            item.value = normalize_assignment_value(
                assignment_definitions[item.assignment_field_definition_id],
                item.value,
            )
        except AssignmentValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        definitions = get_condition_field_definitions(
            session,
            _condition_field_keys(data.condition_group),
        )
    except ConditionFieldError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _validate_employee_condition_references(
        session,
        data.condition_group,
        definitions,
    )
    canonical_root = _build_canonical_condition_tree(
        data.condition_group,
        definitions,
    )
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
        created_by=data.created_by or actor,
        values=[PolicyFieldValue(**item.model_dump()) for item in data.values],
        condition_groups=_collect_condition_groups(canonical_root),
        compiled_clauses=compiled_clauses,
        actor=actor,
    )
    sync_policy_version_schedules(session, policy)
    sync_all_employee_tenure_schedules(session)
    return version


def _validate_assignment_field_definitions(
    session: Session, values
) -> dict[int, AssignmentFieldDefinition]:
    field_ids = {item.assignment_field_definition_id for item in values}
    definitions = {
        item.id: item
        for item in session.scalars(
            select(AssignmentFieldDefinition).where(
                AssignmentFieldDefinition.id.in_(field_ids),
            )
        )
    }
    missing_ids = sorted(field_ids - definitions.keys())
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Assignment field definitions not found: {missing_ids}",
        )
    return definitions


def _build_canonical_condition_tree(
    data: ConditionGroupCreate,
    definitions: dict[str, ConditionFieldDefinition],
) -> ConditionGroup:
    return ConditionGroup(
        logical_operator=data.logical_operator,
        condition_links=[
            ConditionGroupCondition(
                condition=Condition(
                    condition_field_definition=definitions[item.field],
                    operator=item.operator,
                    value=item.value,
                )
            )
            for item in data.conditions
        ],
        child_groups=[
            _build_canonical_condition_tree(child, definitions)
            for child in data.child_groups
        ],
    )


def _condition_field_keys(root: ConditionGroupCreate) -> set[str]:
    return {
        *(condition.field for condition in root.conditions),
        *(
            field_key
            for child in root.child_groups
            for field_key in _condition_field_keys(child)
        ),
    }


def _condition_items(root: ConditionGroupCreate) -> Iterator:
    yield from root.conditions
    for child in root.child_groups:
        yield from _condition_items(child)


def _validate_employee_condition_references(
    session: Session,
    root: ConditionGroupCreate,
    definitions: dict[str, ConditionFieldDefinition],
) -> None:
    employee_ids = {
        int(condition.value)
        for condition in _condition_items(root)
        if definitions[condition.field].data_type == "employee_reference"
    }
    if not employee_ids:
        return
    existing_ids = set(
        session.scalars(select(Employee.id).where(Employee.id.in_(employee_ids)))
    )
    missing_ids = sorted(employee_ids - existing_ids)
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Condition employee references not found: {missing_ids}",
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
