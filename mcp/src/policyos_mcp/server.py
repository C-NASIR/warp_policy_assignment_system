from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations


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
            async with httpx.AsyncClient(base_url=backend_url(), timeout=10.0) as client:
                response = await client.get(
                    "/oauth/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        data = response.json()
        return AccessToken(
            token=token,
            client_id=data["client_id"],
            scopes=data["scopes"],
            expires_at=data["expires_at"],
            resource=data["resource"],
            subject=data["sub"],
            claims={"user_id": data["user_id"]},
        )


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
MUTATING = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
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
        required_scopes=["policyos"],
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
        raise RuntimeError("The MCP request did not include a bearer access token")
    return token


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
                params={key: value for key, value in (params or {}).items() if value is not None},
                json=body,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"PolicyOS backend is unavailable: {exc}") from exc
    if response.status_code >= 400:
        try:
            error = response.json().get("error", {})
            message = error.get("message") or response.text
            code = error.get("code")
        except (ValueError, AttributeError):
            message, code = response.text, None
        label = f" ({code})" if code else ""
        raise RuntimeError(f"PolicyOS rejected the operation{label}: {message}")
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
async def get_employee(ctx: Context, employee_id: int) -> dict[str, Any]:
    """Get one visible employee and their current employment facts."""
    return await _request(ctx, "GET", f"/employees/{employee_id}")


@server.tool(annotations=READ_ONLY)
async def get_employee_assignments(
    ctx: Context,
    employee_id: int,
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
async def query_assignments(ctx: Context, query: dict[str, Any]) -> Any:
    """Query past, current, or future assignments for an employee batch."""
    return await _request(ctx, "POST", "/assignment-queries", body=query)


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
async def get_policy(ctx: Context, policy_id: int) -> dict[str, Any]:
    """Get a policy, its versions, and the actions the user may perform."""
    return await _request(ctx, "GET", f"/policies/{policy_id}")


@server.tool(annotations=READ_ONLY)
async def get_policy_impact(ctx: Context, policy_id: int) -> dict[str, Any]:
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
async def get_group(ctx: Context, group_id: int) -> dict[str, Any]:
    """Get one group and its visible membership summary."""
    return await _request(ctx, "GET", f"/groups/{group_id}")


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
async def preview_change(ctx: Context, change: dict[str, Any]) -> dict[str, Any]:
    """Preview a supported employee, policy, group, or override change without saving it."""
    return await _request(ctx, "POST", "/change-previews", body=change)


@server.tool(annotations=MUTATING)
async def create_employee(ctx: Context, employee: dict[str, Any]) -> dict[str, Any]:
    """Create an employee using the backend's validated employee payload."""
    return await _request(ctx, "POST", "/employees", body=employee)


@server.tool(annotations=MUTATING)
async def update_employee(
    ctx: Context, employee_id: int, changes: dict[str, Any]
) -> dict[str, Any]:
    """Update a visible employee's employment facts."""
    return await _request(ctx, "PATCH", f"/employees/{employee_id}", body=changes)


@server.tool(annotations=MUTATING)
async def create_policy(ctx: Context, policy: dict[str, Any]) -> dict[str, Any]:
    """Create a policy and its initial version after using preview_change."""
    return await _request(ctx, "POST", "/policies", body=policy)


@server.tool(annotations=MUTATING)
async def create_policy_version(
    ctx: Context, policy_id: int, version: dict[str, Any]
) -> dict[str, Any]:
    """Add a version to a policy after using preview_change."""
    return await _request(ctx, "POST", f"/policies/{policy_id}/versions", body=version)


@server.tool(annotations=MUTATING)
async def update_policy(
    ctx: Context, policy_id: int, changes: dict[str, Any]
) -> dict[str, Any]:
    """Update policy metadata or lifecycle state using the backend's policy payload."""
    return await _request(ctx, "PATCH", f"/policies/{policy_id}", body=changes)


@server.tool(annotations=MUTATING)
async def refresh_employee_assignments(ctx: Context, employee_id: int) -> Any:
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
