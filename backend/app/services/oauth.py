from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode, urlparse, urlunparse

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.dates import current_datetime, ensure_utc
from app.models import (
    AuthSession,
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthToken,
    User,
)
from app.schemas import OAuthClientRegistrationCreate
from app.services.human_auth import record_security_event

OAUTH_SCOPE = "policyos"


class OAuthProtocolError(ValueError):
    def __init__(
        self,
        error: str,
        description: str,
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(description)
        self.error = error
        self.description = description
        self.status_code = status_code


@dataclass(frozen=True)
class IssuedOAuthTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    scopes: list[str]


def oauth_issuer_url() -> str:
    return os.getenv("OAUTH_ISSUER_URL", "http://127.0.0.1:8000").rstrip("/")


def oauth_authorization_url() -> str:
    return os.getenv(
        "OAUTH_AUTHORIZATION_URL", "http://localhost:3000/oauth/authorize"
    )


def mcp_resource_url() -> str:
    return os.getenv("MCP_PUBLIC_URL", "http://127.0.0.1:8001/mcp").rstrip("/")


def access_token_ttl_seconds() -> int:
    return _integer_setting("OAUTH_ACCESS_TOKEN_TTL_SECONDS", 3600, 300, 86400)


def refresh_token_ttl_seconds() -> int:
    return _integer_setting(
        "OAUTH_REFRESH_TOKEN_TTL_SECONDS", 30 * 86400, 3600, 90 * 86400
    )


def authorization_code_ttl_seconds() -> int:
    return _integer_setting("OAUTH_CODE_TTL_SECONDS", 300, 60, 600)


def authorization_server_metadata() -> dict:
    issuer = oauth_issuer_url()
    return {
        "issuer": issuer,
        "authorization_endpoint": oauth_authorization_url(),
        "token_endpoint": f"{issuer}/oauth/token",
        "registration_endpoint": f"{issuer}/oauth/register",
        "revocation_endpoint": f"{issuer}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": [OAUTH_SCOPE],
    }


def register_client(
    session: Session, data: OAuthClientRegistrationCreate
) -> OAuthClient:
    redirect_uris = [_validate_redirect_uri(value) for value in data.redirect_uris]
    if len(set(redirect_uris)) != len(redirect_uris):
        raise OAuthProtocolError("invalid_client_metadata", "redirect_uris must be unique")
    client = OAuthClient(
        client_id=f"poc_{secrets.token_urlsafe(24)}",
        client_name=data.client_name.strip(),
        redirect_uris=redirect_uris,
    )
    session.add(client)
    session.flush()
    return client


def validate_authorization_request(
    session: Session,
    *,
    client_id: str,
    redirect_uri: str,
    response_type: str,
    code_challenge: str,
    code_challenge_method: str,
    scope: str | None,
    resource: str | None,
) -> tuple[OAuthClient, list[str], str]:
    client = session.get(OAuthClient, client_id)
    if client is None:
        raise OAuthProtocolError("invalid_request", "The OAuth client is not registered")
    if redirect_uri not in client.redirect_uris:
        raise OAuthProtocolError("invalid_request", "The redirect URI is not registered")
    if response_type != "code":
        raise OAuthProtocolError("unsupported_response_type", "Only code is supported")
    if code_challenge_method != "S256" or not 43 <= len(code_challenge) <= 128:
        raise OAuthProtocolError(
            "invalid_request", "A valid S256 PKCE code challenge is required"
        )
    scopes = _validated_scopes(scope)
    requested_resource = (resource or mcp_resource_url()).rstrip("/")
    if requested_resource != mcp_resource_url():
        raise OAuthProtocolError(
            "invalid_target", "The requested resource is not this PolicyOS MCP server"
        )
    return client, scopes, requested_resource


def authorization_redirect(
    session: Session,
    *,
    user: User,
    auth_session: AuthSession,
    client_id: str,
    redirect_uri: str,
    response_type: str,
    code_challenge: str,
    code_challenge_method: str,
    scope: str | None,
    state: str | None,
    resource: str | None,
    approve: bool,
) -> str:
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
    if not approve:
        return _redirect_with_query(
            redirect_uri,
            {"error": "access_denied", "state": state},
        )

    raw_code = f"pocd_{secrets.token_urlsafe(48)}"
    now = current_datetime()
    session.add(
        OAuthAuthorizationCode(
            code_hash=_hash_token(raw_code),
            client_id=client.client_id,
            user_id=user.id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            scopes=scopes,
            resource=requested_resource,
            created_at=now,
            expires_at=now + timedelta(seconds=authorization_code_ttl_seconds()),
            reauthenticated_at=auth_session.reauthenticated_at,
            mfa_verified=auth_session.mfa_verified_at is not None,
        )
    )
    record_security_event(
        session,
        user=user,
        event_type="agent_access_authorized",
        details={"client_id": client.client_id, "client_name": client.client_name},
    )
    return _redirect_with_query(redirect_uri, {"code": raw_code, "state": state})


def exchange_authorization_code(
    session: Session,
    *,
    client_id: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    resource: str | None,
) -> IssuedOAuthTokens:
    client = session.get(OAuthClient, client_id)
    if client is None:
        raise OAuthProtocolError("invalid_client", "The OAuth client is not registered", status_code=401)
    record = session.scalar(
        select(OAuthAuthorizationCode)
        .where(OAuthAuthorizationCode.code_hash == _hash_token(code))
        .with_for_update()
    )
    now = current_datetime()
    if (
        record is None
        or record.client_id != client_id
        or record.redirect_uri != redirect_uri
        or record.used_at is not None
        or now >= ensure_utc(record.expires_at)
    ):
        raise OAuthProtocolError("invalid_grant", "The authorization code is invalid or expired")
    if resource is not None and resource.rstrip("/") != record.resource:
        raise OAuthProtocolError("invalid_target", "The token resource does not match the authorization request")
    if not _valid_pkce_verifier(code_verifier, record.code_challenge):
        raise OAuthProtocolError("invalid_grant", "PKCE verification failed")
    record.used_at = now
    return _issue_tokens(
        session,
        user_id=record.user_id,
        client_id=record.client_id,
        scopes=list(record.scopes),
        resource=record.resource,
        reauthenticated_at=record.reauthenticated_at,
        mfa_verified=record.mfa_verified,
    )


def exchange_refresh_token(
    session: Session,
    *,
    client_id: str,
    refresh_token: str,
    scope: str | None,
    resource: str | None,
) -> IssuedOAuthTokens:
    record = session.scalar(
        select(OAuthToken)
        .where(OAuthToken.refresh_token_hash == _hash_token(refresh_token))
        .with_for_update()
    )
    now = current_datetime()
    if (
        record is None
        or record.client_id != client_id
        or record.revoked_at is not None
        or now >= ensure_utc(record.refresh_expires_at)
    ):
        raise OAuthProtocolError("invalid_grant", "The refresh token is invalid or expired")
    requested_scopes = _validated_scopes(scope) if scope is not None else list(record.scopes)
    if not set(requested_scopes) <= set(record.scopes):
        raise OAuthProtocolError("invalid_scope", "Refresh cannot increase the granted scope")
    if resource is not None and resource.rstrip("/") != record.resource:
        raise OAuthProtocolError("invalid_target", "The token resource cannot be changed")
    record.revoked_at = now
    return _issue_tokens(
        session,
        user_id=record.user_id,
        client_id=record.client_id,
        scopes=requested_scopes,
        resource=record.resource,
        reauthenticated_at=record.reauthenticated_at,
        mfa_verified=record.mfa_verified,
    )


def find_active_access_token(session: Session, token: str) -> tuple[OAuthToken, User] | None:
    record = session.scalar(
        select(OAuthToken).where(OAuthToken.access_token_hash == _hash_token(token))
    )
    now = current_datetime()
    if (
        record is None
        or record.revoked_at is not None
        or now >= ensure_utc(record.access_expires_at)
    ):
        return None
    user = session.get(User, record.user_id)
    if user is None or user.status != "active" or user.password_change_required:
        return None
    if (
        user.password_changed_at is not None
        and ensure_utc(record.created_at) < ensure_utc(user.password_changed_at)
    ):
        return None
    return record, user


def revoke_oauth_token(session: Session, token: str) -> None:
    token_hash = _hash_token(token)
    record = session.scalar(
        select(OAuthToken).where(
            or_(
                OAuthToken.access_token_hash == token_hash,
                OAuthToken.refresh_token_hash == token_hash,
            )
        )
    )
    if record is not None and record.revoked_at is None:
        record.revoked_at = current_datetime()
        user = session.get(User, record.user_id)
        if user is not None:
            record_security_event(
                session,
                user=user,
                event_type="agent_access_revoked",
                details={"client_id": record.client_id},
            )


def _issue_tokens(
    session: Session,
    *,
    user_id: int,
    client_id: str,
    scopes: list[str],
    resource: str,
    reauthenticated_at,
    mfa_verified: bool,
) -> IssuedOAuthTokens:
    access_token = f"poa_{secrets.token_urlsafe(48)}"
    refresh_token = f"por_{secrets.token_urlsafe(48)}"
    now = current_datetime()
    access_ttl = access_token_ttl_seconds()
    session.add(
        OAuthToken(
            access_token_hash=_hash_token(access_token),
            refresh_token_hash=_hash_token(refresh_token),
            token_prefix=access_token[:12],
            client_id=client_id,
            user_id=user_id,
            scopes=scopes,
            resource=resource,
            created_at=now,
            access_expires_at=now + timedelta(seconds=access_ttl),
            refresh_expires_at=now + timedelta(seconds=refresh_token_ttl_seconds()),
            reauthenticated_at=reauthenticated_at,
            mfa_verified=mfa_verified,
        )
    )
    session.flush()
    return IssuedOAuthTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_ttl,
        scopes=scopes,
    )


def _validated_scopes(scope: str | None) -> list[str]:
    scopes = list(dict.fromkeys((scope or OAUTH_SCOPE).split()))
    if not scopes or set(scopes) != {OAUTH_SCOPE}:
        raise OAuthProtocolError("invalid_scope", f"Only the {OAUTH_SCOPE!r} scope is supported")
    return scopes


def _valid_pkce_verifier(verifier: str, expected_challenge: str) -> bool:
    if not 43 <= len(verifier) <= 128:
        return False
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii", errors="ignore")).digest()
    ).rstrip(b"=").decode("ascii")
    return secrets.compare_digest(challenge, expected_challenge)


def _validate_redirect_uri(value: str) -> str:
    if len(value) > 1000:
        raise OAuthProtocolError("invalid_redirect_uri", "A redirect URI is too long")
    parsed = urlparse(value)
    if parsed.fragment or parsed.username or parsed.password or not parsed.scheme:
        raise OAuthProtocolError("invalid_redirect_uri", "A redirect URI is invalid")
    host = (parsed.hostname or "").casefold()
    loopback = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise OAuthProtocolError(
            "invalid_redirect_uri",
            "Redirect URIs must use HTTPS, except for HTTP loopback clients",
        )
    return value


def _redirect_with_query(uri: str, values: dict[str, str | None]) -> str:
    parsed = urlparse(uri)
    additions = urlencode({key: value for key, value in values.items() if value is not None})
    query = "&".join(part for part in (parsed.query, additions) if part)
    return urlunparse(parsed._replace(query=query))


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _integer_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value
