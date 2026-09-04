from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthSession, User
from app.services.access_control import (
    authorize_permissions,
    effective_permissions,
    required_permissions,
)
from app.services.auth import (
    ACTOR_OVERRIDE_SCOPE,
    AuthenticatedPrincipal,
    AuthenticationError,
    authenticate_token,
    authorize,
    required_scope,
)
from app.services.human_auth import SESSION_COOKIE_NAME, authenticate_session

DatabaseSession = Annotated[Session, Depends(get_db)]

bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="wpa_<opaque credential>",
    description="An API credential issued by POST /auth/credentials",
)

SAFE_SESSION_METHODS = {"GET", "HEAD", "OPTIONS"}


def _require_trusted_session_origin(request: Request) -> None:
    """Reject state-changing cookie requests that did not come from this UI."""
    if request.method.upper() in SAFE_SESSION_METHODS:
        return
    origin = request.headers.get("origin")
    same_origin = str(request.base_url).rstrip("/")
    allowed_origins = set(getattr(request.app.state, "browser_allowed_origins", ()))
    allowed_origins.add(same_origin)
    if origin not in allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user-session request did not come from a trusted origin",
        )


def get_authenticated_principal(
    session: DatabaseSession,
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedPrincipal:
    if credentials is not None:
        if (
            credentials.scheme.lower() != "bearer"
            or not credentials.credentials.strip()
        ):
            raise AuthenticationError(
                "Authorization must contain a bearer credential",
                code="invalid_authorization_header",
            )
        return authenticate_token(session, credentials.credentials)

    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        user, auth_session = authenticate_session(session, session_token)
        _require_trusted_session_origin(request)
        if user.password_change_required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must change your temporary password before using PolicyOS",
            )
        return AuthenticatedPrincipal(
            subject=user.email,
            scopes=frozenset({"*"}) if user.is_root else frozenset(),
            credential_id=None,
            credential_name="human-session",
            authentication_method="human_session",
            user_id=user.id,
            session_id=auth_session.id,
            permissions=effective_permissions(session, user),
        )

    raise AuthenticationError(
        "Authentication is required",
        code="authentication_required",
    )


@dataclass(frozen=True)
class AuthenticatedHumanSession:
    user: User
    session: AuthSession


def get_authenticated_human_session(
    session: DatabaseSession,
    request: Request,
) -> AuthenticatedHumanSession:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        raise AuthenticationError(
            "A user session is required",
            code="authentication_required",
        )
    user, auth_session = authenticate_session(session, session_token)
    _require_trusted_session_origin(request)
    return AuthenticatedHumanSession(user=user, session=auth_session)


Authenticated = Annotated[
    AuthenticatedPrincipal,
    Depends(get_authenticated_principal),
]

HumanSession = Annotated[
    AuthenticatedHumanSession,
    Depends(get_authenticated_human_session),
]


def authorize_operation(request: Request, principal: Authenticated) -> None:
    """Authorize one API operation using its method and public route path."""
    if principal.authentication_method == "human_session":
        authorize_permissions(
            principal.permissions,
            required_permissions(request.method, request.url.path),
        )
    else:
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
