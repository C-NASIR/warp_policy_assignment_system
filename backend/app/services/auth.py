from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dates import current_datetime, ensure_utc
from app.models import APICredential
from app.schemas import APICredentialCreate
from app.services.audit import record_audit_log, snapshot_entity

READ_SCOPE = "read"
PREVIEW_SCOPE = "preview"
EXECUTE_SCOPE = "execute"
AUDIT_SCOPE = "audit"
CREDENTIALS_MANAGE_SCOPE = "credentials:manage"
ACTOR_OVERRIDE_SCOPE = "actor:override"
WILDCARD_SCOPE = "*"

OPERATION_SCOPES = {
    READ_SCOPE: "Read employees, policies, groups, catalogs, and assignments",
    PREVIEW_SCOPE: "Simulate changes without persisting them",
    EXECUTE_SCOPE: "Perform mutations and execute approved changes",
    AUDIT_SCOPE: "Read the audit log",
    CREDENTIALS_MANAGE_SCOPE: "Create, list, and revoke API credentials",
    ACTOR_OVERRIDE_SCOPE: "Set X-Actor to record an approved delegated actor",
}


class AuthenticationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.metadata = metadata or {}


class AuthorizationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        required_scopes: set[str],
        granted_scopes: set[str],
    ) -> None:
        super().__init__(message)
        self.code = "insufficient_scope"
        self.metadata = {
            "required_scopes": sorted(required_scopes),
            "granted_scopes": sorted(granted_scopes),
        }


class CredentialConflictError(ValueError):
    def __init__(self, message: str, *, name: str) -> None:
        super().__init__(message)
        self.code = "credential_name_conflict"
        self.metadata = {"name": name}


class CredentialValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.metadata = metadata or {}


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: str
    scopes: frozenset[str]
    credential_id: int | None
    credential_name: str
    authentication_method: str
    user_id: int | None = None
    session_id: int | None = None

    def has_scope(self, scope: str) -> bool:
        return WILDCARD_SCOPE in self.scopes or scope in self.scopes


def authenticate_token(session: Session, token: str) -> AuthenticatedPrincipal:
    bootstrap_token = os.getenv("AUTH_BOOTSTRAP_TOKEN")
    if (
        bootstrap_token
        and len(bootstrap_token.encode("utf-8")) >= 32
        and hmac.compare_digest(token, bootstrap_token)
    ):
        bootstrap_subject = os.getenv("AUTH_BOOTSTRAP_SUBJECT", "bootstrap").strip()
        if not bootstrap_subject or len(bootstrap_subject) > 200:
            raise AuthenticationError(
                "AUTH_BOOTSTRAP_SUBJECT must contain 1 to 200 characters",
                code="bootstrap_configuration_invalid",
            )
        return AuthenticatedPrincipal(
            subject=bootstrap_subject,
            scopes=frozenset({WILDCARD_SCOPE}),
            credential_id=None,
            credential_name="bootstrap",
            authentication_method="bootstrap_token",
        )

    credential = session.scalar(
        select(APICredential).where(APICredential.token_hash == hash_token(token))
    )
    if credential is None:
        raise AuthenticationError(
            "The bearer credential is invalid",
            code="invalid_credential",
        )
    if credential.revoked_at is not None:
        raise AuthenticationError(
            "The bearer credential has been revoked",
            code="credential_revoked",
            metadata={"credential_id": credential.id},
        )
    if (
        credential.expires_at is not None
        and current_datetime() >= ensure_utc(credential.expires_at)
    ):
        raise AuthenticationError(
            "The bearer credential has expired",
            code="credential_expired",
            metadata={"credential_id": credential.id},
        )
    return AuthenticatedPrincipal(
        subject=credential.subject,
        scopes=frozenset(credential.scopes),
        credential_id=credential.id,
        credential_name=credential.name,
        authentication_method="api_credential",
    )


def authorize(principal: AuthenticatedPrincipal, required_scopes: set[str]) -> None:
    missing = {scope for scope in required_scopes if not principal.has_scope(scope)}
    if missing:
        raise AuthorizationError(
            "The bearer credential does not grant the required operation scope",
            required_scopes=required_scopes,
            granted_scopes=set(principal.scopes),
        )


def required_scope(method: str, path: str) -> str:
    if path.startswith("/auth/credentials"):
        return CREDENTIALS_MANAGE_SCOPE
    if path == "/auth/scopes":
        return READ_SCOPE
    if path.startswith("/audit-logs"):
        return AUDIT_SCOPE
    if path.startswith("/change-previews"):
        return PREVIEW_SCOPE
    if path.startswith("/change-executions"):
        return EXECUTE_SCOPE
    if path.startswith("/assignment-queries"):
        return READ_SCOPE
    if method.upper() == "GET":
        return READ_SCOPE
    return EXECUTE_SCOPE


def create_credential(
    session: Session,
    data: APICredentialCreate,
    principal: AuthenticatedPrincipal,
) -> tuple[APICredential, str]:
    scopes = sorted(set(data.scopes))
    unknown = sorted(set(scopes) - set(OPERATION_SCOPES))
    if unknown:
        raise CredentialValidationError(
            f"Unknown operation scopes: {unknown}",
            code="unknown_operation_scope",
            metadata={"unknown_scopes": unknown},
        )
    if data.expires_at is not None and data.expires_at <= current_datetime():
        raise CredentialValidationError(
            "expires_at must be in the future",
            code="credential_expiry_not_future",
        )
    if (
        session.scalar(select(APICredential.id).where(APICredential.name == data.name))
        is not None
    ):
        raise CredentialConflictError(
            f"API credential '{data.name}' already exists",
            name=data.name,
        )
    token = f"wpa_{secrets.token_urlsafe(32)}"
    credential = APICredential(
        name=data.name,
        subject=data.subject,
        token_prefix=token[:12],
        token_hash=hash_token(token),
        scopes=scopes,
        created_by=principal.subject,
        expires_at=data.expires_at,
    )
    session.add(credential)
    session.flush()
    record_audit_log(
        session,
        actor=principal.subject,
        entity_type="APICredential",
        entity_id=credential.id,
        action="created",
        before=None,
        after=snapshot_entity(credential, exclude={"token_hash"}),
    )
    return credential, token


def list_credentials(session: Session) -> list[APICredential]:
    return list(session.scalars(select(APICredential).order_by(APICredential.id)))


def revoke_credential(
    session: Session,
    credential_id: int,
    principal: AuthenticatedPrincipal,
) -> APICredential:
    credential = session.get(APICredential, credential_id)
    if credential is None:
        raise LookupError(f"API credential {credential_id} not found")
    if credential.revoked_at is None:
        before = snapshot_entity(credential, exclude={"token_hash"})
        credential.revoked_at = current_datetime()
        session.flush()
        record_audit_log(
            session,
            actor=principal.subject,
            entity_type="APICredential",
            entity_id=credential.id,
            action="revoked",
            before=before,
            after=snapshot_entity(credential, exclude={"token_hash"}),
        )
    return credential


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
