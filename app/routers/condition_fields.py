from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import DatabaseSession
from app.models import ConditionFieldDefinition
from app.schemas import ConditionFieldDefinitionRead
from app.services.condition_fields import sync_condition_field_definitions

router = APIRouter(prefix="/condition-fields", tags=["condition fields"])


def _query():
    return select(ConditionFieldDefinition).options(
        selectinload(ConditionFieldDefinition.dependencies)
    )


@router.get("", response_model=list[ConditionFieldDefinitionRead])
def list_all(session: DatabaseSession) -> list[ConditionFieldDefinition]:
    sync_condition_field_definitions(session)
    return list(session.scalars(_query().order_by(ConditionFieldDefinition.id)))


@router.get("/{field_key}", response_model=ConditionFieldDefinitionRead)
def get(field_key: str, session: DatabaseSession) -> ConditionFieldDefinition:
    sync_condition_field_definitions(session)
    definition = session.scalar(
        _query().where(ConditionFieldDefinition.key == field_key)
    )
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Condition field '{field_key}' not found")
    return definition
