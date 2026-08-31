from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import DatabaseSession
from app.models import AssignmentFieldDefinition
from app.schemas import (
    AssignmentFieldDefinitionCreate,
    AssignmentFieldDefinitionRead,
)

router = APIRouter(prefix="/assignment-fields", tags=["assignment fields"])


@router.post(
    "",
    response_model=AssignmentFieldDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: AssignmentFieldDefinitionCreate,
    session: DatabaseSession,
) -> AssignmentFieldDefinition:
    assignment_field = AssignmentFieldDefinition(**data.model_dump())
    session.add(assignment_field)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Assignment field definition '{data.name}' already exists",
        ) from exc
    return assignment_field


@router.get("", response_model=list[AssignmentFieldDefinitionRead])
def list_all(session: DatabaseSession) -> list[AssignmentFieldDefinition]:
    return list(
        session.scalars(
            select(AssignmentFieldDefinition).order_by(AssignmentFieldDefinition.id)
        )
    )


@router.get(
    "/{assignment_field_definition_id}",
    response_model=AssignmentFieldDefinitionRead,
)
def get(
    assignment_field_definition_id: int,
    session: DatabaseSession,
) -> AssignmentFieldDefinition:
    assignment_field = session.get(
        AssignmentFieldDefinition,
        assignment_field_definition_id,
    )
    if assignment_field is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Assignment field definition "
                f"{assignment_field_definition_id} not found"
            ),
        )
    return assignment_field
