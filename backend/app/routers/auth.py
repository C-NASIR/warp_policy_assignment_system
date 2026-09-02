from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from app.dates import current_datetime
from app.dependencies import Authenticated, DatabaseSession
from app.models import APICredential
from app.pagination import Pagination, paginate_scalars, paginate_sequence
from app.schemas import (
    APICredentialCreate,
    APICredentialCreatedRead,
    APICredentialRead,
    OperationScopeRead,
)
from app.services.auth import (
    OPERATION_SCOPES,
    create_credential,
    revoke_credential,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/scopes", response_model=list[OperationScopeRead])
def list_operation_scopes(
    response: Response,
    pagination: Pagination,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> list[OperationScopeRead]:
    scopes = [
        OperationScopeRead(name=name, description=description)
        for name, description in OPERATION_SCOPES.items()
    ]
    if search:
        search_value = search.strip().casefold()
        scopes = [
            scope
            for scope in scopes
            if search_value in scope.name.casefold()
            or search_value in scope.description.casefold()
        ]
    return paginate_sequence(scopes, pagination, response)


@router.post(
    "/credentials",
    response_model=APICredentialCreatedRead,
    status_code=status.HTTP_201_CREATED,
)
def create_api_credential(
    data: APICredentialCreate,
    session: DatabaseSession,
    principal: Authenticated,
) -> APICredentialCreatedRead:
    credential, token = create_credential(session, data, principal)
    return APICredentialCreatedRead(
        **APICredentialRead.model_validate(credential).model_dump(),
        token=token,
    )


@router.get("/credentials", response_model=list[APICredentialRead])
def get_api_credentials(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    search: Annotated[str | None, Query(max_length=200)] = None,
    subject: Annotated[str | None, Query(max_length=200)] = None,
    scope: Annotated[str | None, Query(max_length=100)] = None,
    credential_status: Annotated[
        Literal["active", "expired", "revoked"] | None,
        Query(alias="status"),
    ] = None,
) -> list[APICredential]:
    statement = select(APICredential)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                APICredential.name.ilike(pattern),
                APICredential.subject.ilike(pattern),
                APICredential.token_prefix.ilike(pattern),
            )
        )
    if subject is not None:
        statement = statement.where(APICredential.subject == subject)
    if scope is not None:
        statement = statement.where(
            cast(APICredential.scopes, JSONB).contains([scope])
        )
    now = current_datetime()
    if credential_status == "revoked":
        statement = statement.where(APICredential.revoked_at.is_not(None))
    elif credential_status == "expired":
        statement = statement.where(
            APICredential.revoked_at.is_(None),
            APICredential.expires_at.is_not(None),
            APICredential.expires_at <= now,
        )
    elif credential_status == "active":
        statement = statement.where(
            APICredential.revoked_at.is_(None),
            or_(APICredential.expires_at.is_(None), APICredential.expires_at > now),
        )
    return paginate_scalars(
        session,
        statement.order_by(APICredential.id),
        pagination,
        response,
    )


@router.delete(
    "/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_api_credential(
    credential_id: int,
    session: DatabaseSession,
    principal: Authenticated,
) -> Response:
    try:
        revoke_credential(session, credential_id, principal)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
