from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import DatabaseSession
from app.models import (
    CompiledPolicyClause,
    Condition,
    ConditionGroup,
    ConditionGroupCondition,
    FieldDefinition,
    Policy,
    PolicyFieldValue,
)
from app.schemas import ConditionGroupCreate, PolicyCreate, PolicyRead, PolicyUpdate
from app.services.policy_compiler import (
    PolicyCompilationError,
    compile_policy_clauses,
)

router = APIRouter(prefix="/policies", tags=["policies"])


def _query():
    return select(Policy).options(selectinload(Policy.values))


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


def _compile_policy_clauses_or_422(
    canonical_root: ConditionGroup,
) -> list[CompiledPolicyClause]:
    try:
        return compile_policy_clauses(canonical_root)
    except PolicyCompilationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
def create(data: PolicyCreate, session: DatabaseSession) -> Policy:
    _validate_field_definitions(session, data.values)

    policy = Policy(name=data.name, priority=data.priority)
    policy.values = [PolicyFieldValue(**item.model_dump()) for item in data.values]

    # Representation 1: preserve the canonical, human-editable condition tree.
    canonical_root = _build_canonical_condition_tree(data.condition_group)
    policy.condition_groups = _collect_condition_groups(canonical_root)
    session.add(policy)
    session.flush()

    # Representation 2: derive and persist flat clauses used only for matching.
    policy.compiled_clauses = _compile_policy_clauses_or_422(canonical_root)
    session.flush()
    return session.scalar(_query().where(Policy.id == policy.id))


@router.get("", response_model=list[PolicyRead])
def list_all(session: DatabaseSession) -> list[Policy]:
    return list(session.scalars(_query().order_by(Policy.id)))


@router.patch("/{policy_id}", response_model=PolicyRead)
def patch(policy_id: int, data: PolicyUpdate, session: DatabaseSession) -> Policy:
    policy = session.scalar(_query().where(Policy.id == policy_id))
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    if "condition_group" in data.model_fields_set and data.condition_group is None:
        raise HTTPException(status_code=422, detail="condition_group cannot be null")
    if data.values is not None:
        _validate_field_definitions(session, data.values)

    if data.name is not None:
        policy.name = data.name
    if data.priority is not None:
        policy.priority = data.priority
    if data.values is not None:
        policy.values.clear()
        session.flush()
        policy.values = [PolicyFieldValue(**item.model_dump()) for item in data.values]
    if data.condition_group is not None:
        # Representation 1: replace the canonical, human-editable condition tree.
        canonical_root = _build_canonical_condition_tree(data.condition_group)
        policy.condition_groups = _collect_condition_groups(canonical_root)
        session.flush()

        # Representation 2: regenerate flat matching clauses from the new canonical tree.
        policy.compiled_clauses = _compile_policy_clauses_or_422(canonical_root)
        session.flush()
    return session.scalar(_query().where(Policy.id == policy.id))


@router.get("/{policy_id}", response_model=PolicyRead)
def get(policy_id: int, session: DatabaseSession) -> Policy:
    policy = session.scalar(_query().where(Policy.id == policy_id))
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return policy
