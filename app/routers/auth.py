from fastapi import APIRouter, HTTPException, Response, status

from app.dependencies import Authenticated, DatabaseSession
from app.models import APICredential
from app.schemas import (
    APICredentialCreate,
    APICredentialCreatedRead,
    APICredentialRead,
    OperationScopeRead,
)
from app.services.auth import (
    OPERATION_SCOPES,
    create_credential,
    list_credentials,
    revoke_credential,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/scopes", response_model=list[OperationScopeRead])
def list_operation_scopes() -> list[OperationScopeRead]:
    return [
        OperationScopeRead(name=name, description=description)
        for name, description in OPERATION_SCOPES.items()
    ]


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
def get_api_credentials(session: DatabaseSession) -> list[APICredential]:
    return list_credentials(session)


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
