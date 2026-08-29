from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import DatabaseSession
from app.models import FieldDefinition
from app.schemas import FieldDefinitionCreate, FieldDefinitionRead

router = APIRouter(prefix="/field-definitions", tags=["field definitions"])


@router.post("", response_model=FieldDefinitionRead, status_code=status.HTTP_201_CREATED)
def create(data: FieldDefinitionCreate, session: DatabaseSession) -> FieldDefinition:
    field = FieldDefinition(**data.model_dump())
    session.add(field)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail=f"Field definition '{data.name}' already exists") from exc
    return field


@router.get("", response_model=list[FieldDefinitionRead])
def list_all(session: DatabaseSession) -> list[FieldDefinition]:
    return list(session.scalars(select(FieldDefinition).order_by(FieldDefinition.id)))


@router.get("/{field_definition_id}", response_model=FieldDefinitionRead)
def get(field_definition_id: int, session: DatabaseSession) -> FieldDefinition:
    field = session.get(FieldDefinition, field_definition_id)
    if field is None:
        raise HTTPException(status_code=404, detail=f"Field definition {field_definition_id} not found")
    return field
