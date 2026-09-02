from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.dependencies import DatabaseSession
from app.models import ConditionFieldDefinition
from app.pagination import Pagination, paginate_scalars
from app.schemas import ConditionFieldDefinitionRead
from app.services.condition_fields import sync_condition_field_definitions

router = APIRouter(prefix="/condition-fields", tags=["condition fields"])


def _query():
    return select(ConditionFieldDefinition).options(
        selectinload(ConditionFieldDefinition.dependencies)
    )


@router.get("", response_model=list[ConditionFieldDefinitionRead])
def list_all(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    search: Annotated[str | None, Query(max_length=200)] = None,
    field_type: Literal["static", "derived"] | None = None,
    data_type: Annotated[str | None, Query(max_length=50)] = None,
    active: bool | None = None,
) -> list[ConditionFieldDefinition]:
    sync_condition_field_definitions(session)
    statement = _query()
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                ConditionFieldDefinition.key.ilike(pattern),
                ConditionFieldDefinition.label.ilike(pattern),
                ConditionFieldDefinition.description.ilike(pattern),
            )
        )
    if field_type is not None:
        statement = statement.where(ConditionFieldDefinition.field_type == field_type)
    if data_type is not None:
        statement = statement.where(ConditionFieldDefinition.data_type == data_type)
    if active is not None:
        statement = statement.where(ConditionFieldDefinition.active.is_(active))
    return paginate_scalars(
        session,
        statement.order_by(ConditionFieldDefinition.id),
        pagination,
        response,
    )


@router.get("/{field_key}", response_model=ConditionFieldDefinitionRead)
def get(field_key: str, session: DatabaseSession) -> ConditionFieldDefinition:
    sync_condition_field_definitions(session)
    definition = session.scalar(
        _query().where(ConditionFieldDefinition.key == field_key)
    )
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Condition field '{field_key}' not found")
    return definition
