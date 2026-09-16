from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.dependencies import Authenticated, DatabaseSession, HumanSession
from app.schemas import (
    OAuthAuthorizationDecisionCreate,
    OAuthAuthorizationDecisionRead,
    OAuthAuthorizationRequestRead,
    OAuthClientRegistrationCreate,
    OAuthClientRegistrationRead,
    OAuthTokenRead,
    OAuthUserInfoRead,
)
from app.services.oauth import (
    OAuthProtocolError,
    authorization_redirect,
    authorization_server_metadata,
    authorization_ui_redirect,
    exchange_authorization_code,
    exchange_refresh_token,
    register_client,
    revoke_oauth_token,
    validate_authorization_request,
)

public_router = APIRouter(tags=["OAuth"])
session_router = APIRouter(prefix="/oauth", tags=["OAuth"])
userinfo_router = APIRouter(prefix="/oauth", tags=["OAuth"])


def _oauth_error(exc: OAuthProtocolError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "error_description": exc.description},
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@public_router.get("/.well-known/oauth-authorization-server")
def oauth_metadata() -> dict:
    return authorization_server_metadata()


@public_router.get("/oauth/authorize/start", include_in_schema=False)
def oauth_authorize_start(request: Request) -> RedirectResponse:
    """Launch the browser-based authorization UI from the issuer origin."""
    return RedirectResponse(
        authorization_ui_redirect(request.url.query),
        status_code=302,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@public_router.post(
    "/oauth/register",
    response_model=OAuthClientRegistrationRead,
    status_code=201,
)
def oauth_register(
    data: OAuthClientRegistrationCreate,
    session: DatabaseSession,
) -> OAuthClientRegistrationRead | JSONResponse:
    try:
        client = register_client(session, data)
    except OAuthProtocolError as exc:
        return _oauth_error(exc)
    return OAuthClientRegistrationRead(
        client_id=client.client_id,
        client_name=client.client_name,
        redirect_uris=list(client.redirect_uris),
        application_type=data.application_type,
    )


@session_router.get("/authorize", response_model=OAuthAuthorizationRequestRead)
def oauth_authorize_details(
    session: DatabaseSession,
    identity: HumanSession,
    client_id: Annotated[str, Query(min_length=1, max_length=200)],
    redirect_uri: Annotated[str, Query(min_length=1, max_length=1000)],
    response_type: Annotated[str, Query(max_length=50)],
    code_challenge: Annotated[str, Query(min_length=43, max_length=128)],
    code_challenge_method: Annotated[str, Query(max_length=20)],
    scope: Annotated[str | None, Query(max_length=500)] = None,
    state: Annotated[str | None, Query(max_length=1000)] = None,
    resource: Annotated[str | None, Query(max_length=1000)] = None,
) -> OAuthAuthorizationRequestRead | JSONResponse:
    del identity
    try:
        client, scopes, requested_resource = validate_authorization_request(
            session,
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope,
            resource=resource,
        )
    except OAuthProtocolError as exc:
        return _oauth_error(exc)
    return OAuthAuthorizationRequestRead(
        client_id=client.client_id,
        client_name=client.client_name,
        redirect_uri=redirect_uri,
        scope=" ".join(scopes),
        state=state,
        resource=requested_resource,
    )


@session_router.post("/authorize", response_model=OAuthAuthorizationDecisionRead)
def oauth_authorize_decision(
    data: OAuthAuthorizationDecisionCreate,
    session: DatabaseSession,
    identity: HumanSession,
) -> OAuthAuthorizationDecisionRead | JSONResponse:
    try:
        target = authorization_redirect(
            session,
            user=identity.user,
            auth_session=identity.session,
            client_id=data.client_id,
            redirect_uri=data.redirect_uri,
            response_type=data.response_type,
            code_challenge=data.code_challenge,
            code_challenge_method=data.code_challenge_method,
            scope=data.scope,
            state=data.state,
            resource=data.resource,
            approve=data.approve,
        )
    except OAuthProtocolError as exc:
        return _oauth_error(exc)
    return OAuthAuthorizationDecisionRead(redirect_uri=target)


@public_router.post("/oauth/token", response_model=OAuthTokenRead)
def oauth_token(
    session: DatabaseSession,
    grant_type: Annotated[str, Form()],
    client_id: Annotated[str, Form()],
    code: Annotated[str | None, Form()] = None,
    redirect_uri: Annotated[str | None, Form()] = None,
    code_verifier: Annotated[str | None, Form()] = None,
    refresh_token: Annotated[str | None, Form()] = None,
    scope: Annotated[str | None, Form()] = None,
    resource: Annotated[str | None, Form()] = None,
) -> OAuthTokenRead | JSONResponse:
    try:
        if grant_type == "authorization_code":
            if not code or not redirect_uri or not code_verifier:
                raise OAuthProtocolError(
                    "invalid_request",
                    "code, redirect_uri, and code_verifier are required",
                )
            issued = exchange_authorization_code(
                session,
                client_id=client_id,
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
                resource=resource,
            )
        elif grant_type == "refresh_token":
            if not refresh_token:
                raise OAuthProtocolError("invalid_request", "refresh_token is required")
            issued = exchange_refresh_token(
                session,
                client_id=client_id,
                refresh_token=refresh_token,
                scope=scope,
                resource=resource,
            )
        else:
            raise OAuthProtocolError(
                "unsupported_grant_type", "The requested grant type is not supported"
            )
    except OAuthProtocolError as exc:
        return _oauth_error(exc)
    return OAuthTokenRead(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        expires_in=issued.expires_in,
        scope=" ".join(issued.scopes),
    )


@public_router.post("/oauth/revoke", status_code=200)
def oauth_revoke(
    session: DatabaseSession,
    token: Annotated[str, Form()],
    token_type_hint: Annotated[str | None, Form()] = None,
) -> dict:
    del token_type_hint
    revoke_oauth_token(session, token)
    return {}


@userinfo_router.get("/userinfo", response_model=OAuthUserInfoRead)
def oauth_userinfo(principal: Authenticated) -> OAuthUserInfoRead:
    if not principal.is_user or principal.authentication_method != "oauth_access_token":
        from app.services.auth import AuthenticationError

        raise AuthenticationError(
            "An OAuth user access token is required",
            code="invalid_credential",
        )
    assert principal.user_id is not None
    assert principal.client_id is not None
    assert principal.expires_at is not None
    assert principal.resource is not None
    return OAuthUserInfoRead(
        sub=principal.subject,
        user_id=principal.user_id,
        client_id=principal.client_id,
        scopes=sorted(principal.scopes),
        expires_at=int(principal.expires_at.timestamp()),
        resource=principal.resource,
    )
