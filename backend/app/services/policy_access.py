from __future__ import annotations

from fastapi import HTTPException, status

from app.models import Policy
from app.schemas import PolicyCapabilitiesRead, PolicyRead
from app.services.access_control import WILDCARD_PERMISSION, PermissionDeniedError
from app.services.auth import EXECUTE_SCOPE, WILDCARD_SCOPE, AuthenticatedPrincipal


def _has_permission(principal: AuthenticatedPrincipal, permission: str) -> bool:
    if principal.authentication_method != "human_session":
        return WILDCARD_SCOPE in principal.scopes or EXECUTE_SCOPE in principal.scopes
    return (
        WILDCARD_PERMISSION in principal.permissions
        or permission in principal.permissions
    )


def require_policy_permission(
    principal: AuthenticatedPrincipal,
    permission: str,
) -> None:
    if _has_permission(principal, permission):
        return
    raise PermissionDeniedError(
        required={permission},
        granted=set(principal.permissions),
    )


def policy_capabilities(
    principal: AuthenticatedPrincipal,
    policy: Policy,
) -> PolicyCapabilitiesRead:
    can_activate_permission = _has_permission(principal, "policies:activate")
    can_create_version_permission = _has_permission(
        principal,
        "policies:version:create",
    )
    return PolicyCapabilitiesRead(
        can_update=_has_permission(principal, "policies:update"),
        can_create_version=(
            can_create_version_permission
            and policy.status != "archived"
            and (policy.status == "draft" or can_activate_permission)
        ),
        can_activate=(policy.status != "active" and can_activate_permission),
        can_archive=(
            policy.status != "archived"
            and _has_permission(principal, "policies:archive")
        ),
    )


def require_policy_version_create(
    principal: AuthenticatedPrincipal,
    policy: Policy,
) -> None:
    require_policy_permission(principal, "policies:version:create")
    if policy.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived policies must be activated before adding a version",
        )
    if policy.status == "active" and not _has_permission(
        principal,
        "policies:activate",
    ):
        raise PermissionDeniedError(
            required={"policies:activate"},
            granted=set(principal.permissions),
        )


def policy_read(
    principal: AuthenticatedPrincipal,
    policy: Policy,
) -> PolicyRead:
    value = PolicyRead.model_validate(policy)
    return value.model_copy(
        update={"capabilities": policy_capabilities(principal, policy)}
    )
