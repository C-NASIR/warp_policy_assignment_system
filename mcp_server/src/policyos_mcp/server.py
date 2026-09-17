from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from policyos_mcp.schemas import (
    AssignmentFieldCreateInput,
    AssignmentFieldUpdateInput,
    AssignmentQueryInput,
    ChangePreviewInput,
    EmployeeCreateInput,
    EmployeeOverrideCreateInput,
    EmployeeOverrideUpdateInput,
    EmployeeUpdateInput,
    GroupName,
    PolicyCreateInput,
    PolicyUpdateInput,
    PolicyVersionInput,
    PositiveId,
    RoleCreateInput,
    RoleUpdateInput,
    TemporaryPassword,
    UserCreateInput,
    UserUpdateInput,
)

OAUTH_SCOPE = "policyos"


def backend_url() -> str:
    return os.getenv("POLICYOS_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def issuer_url() -> str:
    return os.getenv("POLICYOS_OAUTH_ISSUER", backend_url()).rstrip("/")


def public_url() -> str:
    return os.getenv("POLICYOS_MCP_PUBLIC_URL", "http://127.0.0.1:8001/mcp").rstrip("/")


class BackendTokenVerifier(TokenVerifier):
    """Validate MCP bearer tokens against the PolicyOS backend."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            async with httpx.AsyncClient(
                base_url=backend_url(), timeout=10.0
            ) as client:
                response = await client.get(
                    "/oauth/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        data = response.json()
        scopes = data["scopes"]
        if OAUTH_SCOPE not in scopes:
            return None
        return AccessToken(
            token=token,
            client_id=data["client_id"],
            scopes=scopes,
            expires_at=data["expires_at"],
            resource=data["resource"],
            subject=data["sub"],
            claims={"user_id": data["user_id"]},
        )


READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
MUTATING = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)
DESTRUCTIVE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
    open_world_hint=False,
)


server = MCPServer(
    name="policyos",
    title="PolicyOS",
    description="Manage workforce policies and inspect explainable employee assignments.",
    instructions=(
        "Use read tools to identify records before changing them. Use preview_change "
        "before material policy or employee changes. Every operation is authorized as "
        "the connected PolicyOS user and is subject to that user's visibility."
    ),
    token_verifier=BackendTokenVerifier(),
    auth=AuthSettings(
        issuer_url=issuer_url(),
        resource_server_url=public_url(),
        # The verifier still enforces PolicyOS's fixed scope. Omitting it from
        # discovery avoids Codex retrying an explicit access_denied response.
        required_scopes=None,
        validate_token_resource=True,
    ),
)


def _bearer_token(ctx: Context) -> str:
    headers = ctx.headers or {}
    authorization = next(
        (value for key, value in headers.items() if key.casefold() == "authorization"),
        "",
    )
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token:
        raise ToolError("The MCP request did not include a bearer access token")
    return token


def _payload(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json", exclude_unset=True)


def _backend_tool_error(response: httpx.Response) -> ToolError:
    status = response.status_code
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        error = payload["error"]
        category = str(error.get("category") or "request")
        code = str(error.get("code") or "backend_error")
        message = str(error.get("message") or "The backend rejected the request")
        details = {
            "http_status": status,
            "category": category,
            "code": code,
            "message": message,
            "issues": error.get("issues")
            if isinstance(error.get("issues"), list)
            else [],
        }
        return ToolError(
            f"PolicyOS {category} error (HTTP {status}, {code}): {message}\n"
            f"Details: {json.dumps(details, separators=(',', ':'), ensure_ascii=False)}"
        )

    body = response.text.strip()
    if len(body) > 2000:
        body = f"{body[:2000]}…"
    message = body or "The backend returned an empty error response"
    return ToolError(f"PolicyOS backend error (HTTP {status}): {message}")


async def _request(
    ctx: Context,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | list[Any] | None = None,
) -> Any:
    headers = {
        "Authorization": f"Bearer {_bearer_token(ctx)}",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(base_url=backend_url(), timeout=30.0) as client:
            response = await client.request(
                method,
                path,
                params={
                    key: value
                    for key, value in (params or {}).items()
                    if value is not None
                },
                json=body,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise ToolError(f"PolicyOS backend is unavailable: {exc}") from exc
    if response.status_code >= 400:
        raise _backend_tool_error(response)
    if response.status_code == 204 or not response.content:
        return {"ok": True}
    payload = response.json()
    if response.headers.get("x-total-count") is not None:
        return {
            "items": payload,
            "page": {
                "total": int(response.headers["x-total-count"]),
                "limit": int(response.headers["x-limit"]),
                "offset": int(response.headers["x-offset"]),
            },
        }
    return payload


@server.tool(annotations=READ_ONLY)
async def search_employees(
    ctx: Context,
    search: str | None = None,
    department: str | None = None,
    state: str | None = None,
    employee_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Search employees visible to the connected user."""
    return await _request(
        ctx,
        "GET",
        "/employees",
        params={
            "search": search,
            "department": department,
            "state": state,
            "employee_type": employee_type,
            "limit": limit,
            "offset": offset,
        },
    )


@server.tool(annotations=READ_ONLY)
async def get_employee(ctx: Context, employee_id: PositiveId) -> dict[str, Any]:
    """Get one visible employee and their current employment facts."""
    return await _request(ctx, "GET", f"/employees/{employee_id}")


@server.tool(annotations=READ_ONLY)
async def get_employee_reference_data(ctx: Context) -> dict[str, Any]:
    """List the states, departments, and employee types used by employee forms."""
    return await _request(ctx, "GET", "/employees/reference-data")


@server.tool(annotations=READ_ONLY)
async def search_manager_candidates(
    ctx: Context,
    search: str | None = None,
    employee_id: PositiveId | None = None,
    limit: int = 20,
) -> Any:
    """Find visible employees who can be selected as an employee's manager."""
    return await _request(
        ctx,
        "GET",
        "/employees/manager-candidates",
        params={"search": search, "employee_id": employee_id, "limit": limit},
    )


@server.tool(annotations=READ_ONLY)
async def get_employee_assignments(
    ctx: Context,
    employee_id: PositiveId,
    as_of: str | None = None,
) -> Any:
    """Read an employee's assignments, optionally at an ISO-8601 timestamp."""
    return await _request(
        ctx,
        "GET",
        f"/employees/{employee_id}/assignments",
        params={"as_of": as_of, "limit": 500, "offset": 0},
    )


@server.tool(annotations=READ_ONLY)
async def get_employee_assignment_history(
    ctx: Context,
    employee_id: PositiveId,
    status: str = "inactive",
    assignment_field_definition_id: PositiveId | None = None,
    value: str | None = None,
    source: str | None = None,
    effective_from: str | None = None,
    effective_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """Read historical assignments for a visible employee."""
    return await _request(
        ctx,
        "GET",
        f"/employees/{employee_id}/assignments/history",
        params={
            "status": status,
            "assignment_field_definition_id": assignment_field_definition_id,
            "value": value,
            "source": source,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "limit": limit,
            "offset": offset,
        },
    )


@server.tool(annotations=READ_ONLY)
async def list_employee_override_options(ctx: Context, employee_id: PositiveId) -> Any:
    """List assignment fields that can be manually overridden for an employee."""
    return await _request(ctx, "GET", f"/employees/{employee_id}/overrides/options")


@server.tool(annotations=READ_ONLY)
async def list_employee_overrides(
    ctx: Context,
    employee_id: PositiveId,
    assignment_field_definition_id: PositiveId | None = None,
    value: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List manual assignment overrides for a visible employee."""
    return await _request(
        ctx,
        "GET",
        f"/employees/{employee_id}/overrides",
        params={
            "assignment_field_definition_id": assignment_field_definition_id,
            "value": value,
            "limit": limit,
            "offset": offset,
        },
    )


@server.tool(annotations=READ_ONLY)
async def query_assignments(ctx: Context, query: AssignmentQueryInput) -> Any:
    """Query past, current, or future assignments for an employee batch."""
    return await _request(ctx, "POST", "/assignment-queries", body=_payload(query))


@server.tool(annotations=READ_ONLY)
async def list_policies(
    ctx: Context,
    search: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List policies visible through the user's assignment-field scope."""
    return await _request(
        ctx,
        "GET",
        "/policies",
        params={"search": search, "status": status, "limit": limit, "offset": offset},
    )


@server.tool(annotations=READ_ONLY)
async def get_policy(ctx: Context, policy_id: PositiveId) -> dict[str, Any]:
    """Get a policy, its versions, and the actions the user may perform."""
    return await _request(ctx, "GET", f"/policies/{policy_id}")


@server.tool(annotations=READ_ONLY)
async def get_policy_impact(ctx: Context, policy_id: PositiveId) -> dict[str, Any]:
    """Explain which visible employees and assignments a policy affects."""
    return await _request(ctx, "GET", f"/policies/{policy_id}/impact-summary")


@server.tool(annotations=READ_ONLY)
async def list_groups(
    ctx: Context,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List visible employee groups."""
    return await _request(
        ctx,
        "GET",
        "/groups",
        params={"search": search, "limit": limit, "offset": offset},
    )


@server.tool(annotations=READ_ONLY)
async def get_group(ctx: Context, group_id: PositiveId) -> dict[str, Any]:
    """Get one group and its visible membership summary."""
    return await _request(ctx, "GET", f"/groups/{group_id}")


@server.tool(annotations=READ_ONLY)
async def list_group_employees(
    ctx: Context,
    group_id: PositiveId,
    search: str | None = None,
    state: str | None = None,
    department: str | None = None,
    employee_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List visible employees belonging to a group."""
    return await _request(
        ctx,
        "GET",
        f"/groups/{group_id}/employees",
        params={
            "search": search,
            "state": state,
            "department": department,
            "employee_type": employee_type,
            "limit": limit,
            "offset": offset,
        },
    )


@server.tool(annotations=READ_ONLY)
async def list_group_policies(
    ctx: Context,
    group_id: PositiveId,
    search: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List visible policies attached to a group."""
    return await _request(
        ctx,
        "GET",
        f"/groups/{group_id}/policies",
        params={
            "search": search,
            "status": status,
            "limit": limit,
            "offset": offset,
        },
    )


@server.tool(annotations=READ_ONLY)
async def list_assignment_fields(ctx: Context) -> Any:
    """List assignment output fields the user may access."""
    return await _request(
        ctx, "GET", "/assignment-fields", params={"limit": 500, "offset": 0}
    )


@server.tool(annotations=READ_ONLY)
async def list_condition_fields(ctx: Context) -> Any:
    """List supported policy condition inputs, operators, and value contracts."""
    return await _request(
        ctx, "GET", "/condition-fields", params={"limit": 500, "offset": 0}
    )


@server.tool(annotations=READ_ONLY)
async def get_assignment_summary(
    ctx: Context, evaluation_date: str | None = None
) -> dict[str, Any]:
    """Read the assignment summary used by the dashboard."""
    return await _request(
        ctx, "GET", "/assignment-summary", params={"evaluation_date": evaluation_date}
    )


@server.tool(annotations=READ_ONLY)
async def get_audit_log_facets(ctx: Context) -> dict[str, Any]:
    """List visible audit entity types and actions for audit filtering."""
    return await _request(ctx, "GET", "/audit-logs/facets")


@server.tool(annotations=READ_ONLY)
async def search_audit_log(
    ctx: Context,
    search: str | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Search audit events within the user's data visibility."""
    return await _request(
        ctx,
        "GET",
        "/audit-logs",
        params={
            "search": search,
            "entity_type": entity_type,
            "action": action,
            "sort": "desc",
            "limit": limit,
            "offset": offset,
        },
    )


@server.tool(annotations=READ_ONLY)
async def list_permissions(ctx: Context, limit: int = 500, offset: int = 0) -> Any:
    """List permissions available for role configuration."""
    return await _request(
        ctx,
        "GET",
        "/authorization/permissions",
        params={"limit": limit, "offset": offset},
    )


@server.tool(annotations=READ_ONLY)
async def get_access_review(ctx: Context) -> dict[str, Any]:
    """Read the current authorization access review."""
    return await _request(ctx, "GET", "/authorization/access-review")


@server.tool(annotations=READ_ONLY)
async def list_authorization_assignment_fields(ctx: Context) -> Any:
    """List assignment-field scope options used to configure roles."""
    return await _request(ctx, "GET", "/authorization/assignment-fields")


@server.tool(annotations=READ_ONLY)
async def search_role_candidates(
    ctx: Context,
    search: str | None = None,
    role_id: PositiveId | None = None,
    limit: int = 20,
) -> Any:
    """Find roles for user assignment and access filtering."""
    return await _request(
        ctx,
        "GET",
        "/authorization/role-candidates",
        params={"search": search, "role_id": role_id, "limit": limit},
    )


@server.tool(annotations=READ_ONLY)
async def search_employee_candidates(
    ctx: Context,
    search: str | None = None,
    user_id: PositiveId | None = None,
    limit: int = 20,
) -> Any:
    """Find visible employees that can be linked to a user account."""
    return await _request(
        ctx,
        "GET",
        "/authorization/employee-candidates",
        params={"search": search, "user_id": user_id, "limit": limit},
    )


@server.tool(annotations=READ_ONLY)
async def list_roles(
    ctx: Context,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List configured authorization roles."""
    return await _request(
        ctx,
        "GET",
        "/roles",
        params={"search": search, "limit": limit, "offset": offset},
    )


@server.tool(annotations=READ_ONLY)
async def get_role(ctx: Context, role_id: PositiveId) -> dict[str, Any]:
    """Get one authorization role and its full configuration."""
    return await _request(ctx, "GET", f"/roles/{role_id}")


@server.tool(annotations=READ_ONLY)
async def list_users(
    ctx: Context,
    search: str | None = None,
    status: str | None = None,
    role_id: PositiveId | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List human user accounts visible to the connected administrator."""
    return await _request(
        ctx,
        "GET",
        "/users",
        params={
            "search": search,
            "status": status,
            "role_id": role_id,
            "limit": limit,
            "offset": offset,
        },
    )


@server.tool(annotations=READ_ONLY)
async def preview_change(ctx: Context, change: ChangePreviewInput) -> dict[str, Any]:
    """Preview a supported employee, policy, group, or override change without saving it."""
    return await _request(ctx, "POST", "/change-previews", body=_payload(change))


@server.tool(annotations=MUTATING)
async def create_employee(
    ctx: Context, employee: EmployeeCreateInput
) -> dict[str, Any]:
    """Create an employee using the backend's validated employee payload."""
    return await _request(ctx, "POST", "/employees", body=_payload(employee))


@server.tool(annotations=MUTATING)
async def update_employee(
    ctx: Context, employee_id: PositiveId, changes: EmployeeUpdateInput
) -> dict[str, Any]:
    """Update name, state, department, employee type, location, start date, or manager.

    Use name for the employee's full name; first_name and last_name are not supported.
    """
    return await _request(
        ctx, "PATCH", f"/employees/{employee_id}", body=_payload(changes)
    )


@server.tool(annotations=MUTATING)
async def create_employee_override(
    ctx: Context, employee_id: PositiveId, override: EmployeeOverrideCreateInput
) -> dict[str, Any]:
    """Create a manual assignment override after using preview_change."""
    return await _request(
        ctx, "POST", f"/employees/{employee_id}/overrides", body=_payload(override)
    )


@server.tool(annotations=MUTATING)
async def update_employee_override(
    ctx: Context,
    employee_id: PositiveId,
    override_id: PositiveId,
    changes: EmployeeOverrideUpdateInput,
) -> dict[str, Any]:
    """Update a manual assignment override after using preview_change."""
    return await _request(
        ctx,
        "PATCH",
        f"/employees/{employee_id}/overrides/{override_id}",
        body=_payload(changes),
    )


@server.tool(annotations=DESTRUCTIVE)
async def delete_employee_override(
    ctx: Context, employee_id: PositiveId, override_id: PositiveId
) -> dict[str, Any]:
    """Delete a manual assignment override after using preview_change."""
    return await _request(
        ctx, "DELETE", f"/employees/{employee_id}/overrides/{override_id}"
    )


@server.tool(annotations=MUTATING)
async def create_policy(ctx: Context, policy: PolicyCreateInput) -> dict[str, Any]:
    """Create a policy and its initial version after using preview_change."""
    return await _request(ctx, "POST", "/policies", body=_payload(policy))


@server.tool(annotations=MUTATING)
async def create_policy_version(
    ctx: Context, policy_id: PositiveId, version: PolicyVersionInput
) -> dict[str, Any]:
    """Add a version to a policy after using preview_change."""
    return await _request(
        ctx, "POST", f"/policies/{policy_id}/versions", body=_payload(version)
    )


@server.tool(annotations=MUTATING)
async def update_policy(
    ctx: Context, policy_id: PositiveId, changes: PolicyUpdateInput
) -> dict[str, Any]:
    """Update policy metadata or lifecycle state using the backend's policy payload."""
    return await _request(
        ctx, "PATCH", f"/policies/{policy_id}", body=_payload(changes)
    )


@server.tool(annotations=MUTATING)
async def create_assignment_field(
    ctx: Context, assignment_field: AssignmentFieldCreateInput
) -> dict[str, Any]:
    """Create an assignment field using the backend's validated payload."""
    return await _request(
        ctx, "POST", "/assignment-fields", body=_payload(assignment_field)
    )


@server.tool(annotations=MUTATING)
async def update_assignment_field(
    ctx: Context,
    assignment_field_id: PositiveId,
    changes: AssignmentFieldUpdateInput,
) -> dict[str, Any]:
    """Update the allowed input values for an assignment field."""
    return await _request(
        ctx,
        "PATCH",
        f"/assignment-fields/{assignment_field_id}",
        body=_payload(changes),
    )


@server.tool(annotations=MUTATING)
async def create_group(ctx: Context, name: GroupName) -> dict[str, Any]:
    """Create an employee group."""
    return await _request(ctx, "POST", "/groups", body={"name": name})


@server.tool(annotations=MUTATING)
async def update_group(
    ctx: Context, group_id: PositiveId, name: GroupName
) -> dict[str, Any]:
    """Rename an employee group."""
    return await _request(ctx, "PATCH", f"/groups/{group_id}", body={"name": name})


@server.tool(annotations=MUTATING)
async def update_group_employees(
    ctx: Context,
    group_id: PositiveId,
    add_employee_ids: list[PositiveId],
    remove_employee_ids: list[PositiveId],
) -> dict[str, Any]:
    """Add employees to and remove employees from a group in one operation."""
    return await _request(
        ctx,
        "PATCH",
        f"/groups/{group_id}/employees",
        body={
            "add_employee_ids": add_employee_ids,
            "remove_employee_ids": remove_employee_ids,
        },
    )


@server.tool(annotations=MUTATING)
async def update_group_policies(
    ctx: Context,
    group_id: PositiveId,
    add_policy_ids: list[PositiveId],
    remove_policy_ids: list[PositiveId],
) -> dict[str, Any]:
    """Attach policies to and remove policies from a group in one operation."""
    return await _request(
        ctx,
        "PATCH",
        f"/groups/{group_id}/policies",
        body={
            "add_policy_ids": add_policy_ids,
            "remove_policy_ids": remove_policy_ids,
        },
    )


@server.tool(annotations=MUTATING)
async def create_role(ctx: Context, role: RoleCreateInput) -> dict[str, Any]:
    """Create an authorization role using the backend's validated payload."""
    return await _request(ctx, "POST", "/roles", body=_payload(role))


@server.tool(annotations=MUTATING)
async def update_role(
    ctx: Context, role_id: PositiveId, changes: RoleUpdateInput
) -> dict[str, Any]:
    """Update an authorization role."""
    return await _request(ctx, "PATCH", f"/roles/{role_id}", body=_payload(changes))


@server.tool(annotations=DESTRUCTIVE)
async def delete_role(ctx: Context, role_id: PositiveId) -> dict[str, Any]:
    """Delete an authorization role that is not assigned to users."""
    return await _request(ctx, "DELETE", f"/roles/{role_id}")


@server.tool(annotations=MUTATING)
async def create_user(ctx: Context, user: UserCreateInput) -> dict[str, Any]:
    """Create a human user account with roles and an optional employee link."""
    return await _request(ctx, "POST", "/users", body=_payload(user))


@server.tool(annotations=MUTATING)
async def update_user(
    ctx: Context, user_id: PositiveId, changes: UserUpdateInput
) -> dict[str, Any]:
    """Update a human user's name, status, roles, or employee link."""
    return await _request(ctx, "PATCH", f"/users/{user_id}", body=_payload(changes))


@server.tool(annotations=DESTRUCTIVE)
async def reset_user_password(
    ctx: Context, user_id: PositiveId, temporary_password: TemporaryPassword
) -> dict[str, Any]:
    """Reset a user's password to a temporary value that must be changed."""
    return await _request(
        ctx,
        "POST",
        f"/users/{user_id}/reset-password",
        body={"temporary_password": temporary_password},
    )


@server.tool(annotations=DESTRUCTIVE)
async def disable_user(ctx: Context, user_id: PositiveId) -> dict[str, Any]:
    """Disable a human user account and revoke its active sessions."""
    return await _request(ctx, "DELETE", f"/users/{user_id}")


@server.tool(annotations=MUTATING)
async def refresh_employee_assignments(ctx: Context, employee_id: PositiveId) -> Any:
    """Reconcile and persist one visible employee's current assignments."""
    return await _request(ctx, "POST", f"/employees/{employee_id}/refresh")


def main() -> None:
    server.run(
        transport="streamable-http",
        host=os.getenv("POLICYOS_MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("POLICYOS_MCP_PORT", "8001")),
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
