from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth import (
    ACTOR_OVERRIDE_SCOPE,
    AuthenticatedPrincipal,
    AuthenticationError,
    authenticate_token,
    authorize,
    required_scope,
)

DatabaseSession = Annotated[Session, Depends(get_db)]

bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="wpa_<opaque credential>",
    description="An API credential issued by POST /auth/credentials",
)


def get_authenticated_principal(
    session: DatabaseSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedPrincipal:
    if credentials is None:
        raise AuthenticationError(
            "A bearer credential is required",
            code="authentication_required",
        )
    if (
        credentials.scheme.lower() != "bearer"
        or not credentials.credentials.strip()
    ):
        raise AuthenticationError(
            "Authorization must contain a bearer credential",
            code="invalid_authorization_header",
        )
    return authenticate_token(session, credentials.credentials)


Authenticated = Annotated[
    AuthenticatedPrincipal,
    Depends(get_authenticated_principal),
]


def authorize_operation(request: Request, principal: Authenticated) -> None:
    """Authorize one API operation using its method and public route path."""
    authorize(principal, {required_scope(request.method, request.url.path)})
    request.state.authenticated_principal = principal


def get_audit_actor(
    principal: Authenticated,
    x_actor: Annotated[str | None, Header()] = None,
) -> str:
    """Use the credential subject unless delegated attribution is authorized."""
    if x_actor is None:
        return principal.subject
    actor = x_actor.strip()
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Actor cannot be blank",
        )
    if len(actor) > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Actor cannot exceed 200 characters",
        )
    authorize(principal, {ACTOR_OVERRIDE_SCOPE})
    return actor


AuditActor = Annotated[str, Depends(get_audit_actor)]
