from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import DatabaseSession
from app.models import (
    Condition,
    ConditionGroup,
    ConditionGroupCondition,
    FieldDefinition,
    Policy,
    PolicyFieldValue,
)
from app.schemas import ConditionGroupCreate, PolicyCreate, PolicyRead, PolicyUpdate
from app.services.policy_compiler import PolicyCompilationError, recompile_policy

router = APIRouter(prefix="/policies", tags=["policies"])


def _query():
    return select(Policy).options(selectinload(Policy.values))


def _validate_field_definitions(session: DatabaseSession, values) -> None:
    field_ids = {item.field_definition_id for item in values}
    existing_ids = set(session.scalars(select(FieldDefinition.id).where(FieldDefinition.id.in_(field_ids))))
    missing_ids = sorted(field_ids - existing_ids)
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Field definitions not found: {missing_ids}")


def _condition_group_from_schema(data: ConditionGroupCreate) -> ConditionGroup:
    return ConditionGroup(
        logical_operator=data.logical_operator,
        condition_links=[
            ConditionGroupCondition(
                condition=Condition(field=item.field, operator=item.operator, value=item.value)
            )
            for item in data.conditions
        ],
        child_groups=[_condition_group_from_schema(child) for child in data.child_groups],
    )


def _flatten_condition_groups(root: ConditionGroup) -> list[ConditionGroup]:
    return [root, *(group for child in root.child_groups for group in _flatten_condition_groups(child))]


@router.post("", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
def create(data: PolicyCreate, session: DatabaseSession) -> Policy:
    _validate_field_definitions(session, data.values)

    policy = Policy(name=data.name, priority=data.priority)
    policy.values = [PolicyFieldValue(**item.model_dump()) for item in data.values]
    root = _condition_group_from_schema(data.condition_group)
    policy.condition_groups = _flatten_condition_groups(root)
    session.add(policy)
    session.flush()
    recompile_policy(session, policy)
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
        root = _condition_group_from_schema(data.condition_group)
        policy.condition_groups = _flatten_condition_groups(root)

    try:
        recompile_policy(session, policy)
    except PolicyCompilationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return session.scalar(_query().where(Policy.id == policy.id))


@router.get("/{policy_id}", response_model=PolicyRead)
def get(policy_id: int, session: DatabaseSession) -> Policy:
    policy = session.scalar(_query().where(Policy.id == policy_id))
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return policy
