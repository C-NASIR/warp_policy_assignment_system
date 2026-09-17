import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from starlette.testclient import TestClient

import policyos_mcp.server as server_module
from policyos_mcp.server import server


def test_server_advertises_oauth_protected_resource_metadata():
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )
    with TestClient(app) as client:
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.status_code == 200
        assert metadata.json() == {
            "resource": "http://127.0.0.1:8001/mcp",
            "authorization_servers": ["http://127.0.0.1:8000"],
            "bearer_methods_supported": ["header"],
        }

        unauthenticated = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
        )
        assert unauthenticated.status_code == 401
        assert "resource_metadata=" in unauthenticated.headers["www-authenticate"]


def test_tool_catalog_covers_frontend_product_operations_and_marks_mutations():
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    assert set(tools) == {
        "search_employees",
        "get_employee",
        "get_employee_reference_data",
        "search_manager_candidates",
        "get_employee_assignments",
        "get_employee_assignment_history",
        "list_employee_override_options",
        "list_employee_overrides",
        "query_assignments",
        "list_policies",
        "get_policy",
        "get_policy_impact",
        "list_groups",
        "get_group",
        "list_group_employees",
        "list_group_policies",
        "list_assignment_fields",
        "list_condition_fields",
        "get_assignment_summary",
        "get_audit_log_facets",
        "search_audit_log",
        "list_permissions",
        "get_access_review",
        "list_authorization_assignment_fields",
        "search_role_candidates",
        "search_employee_candidates",
        "list_roles",
        "get_role",
        "list_users",
        "preview_change",
        "create_employee",
        "update_employee",
        "create_employee_override",
        "update_employee_override",
        "delete_employee_override",
        "create_policy",
        "create_policy_version",
        "update_policy",
        "create_assignment_field",
        "update_assignment_field",
        "create_group",
        "update_group",
        "update_group_employees",
        "update_group_policies",
        "create_role",
        "update_role",
        "delete_role",
        "create_user",
        "update_user",
        "reset_user_password",
        "disable_user",
        "refresh_employee_assignments",
    }
    assert tools["search_employees"].annotations is not None
    assert tools["preview_change"].annotations is not None
    assert tools["create_employee"].annotations is not None
    assert tools["delete_employee_override"].annotations is not None
    assert tools["search_employees"].annotations.read_only_hint is True
    assert tools["preview_change"].annotations.read_only_hint is True
    assert tools["create_employee"].annotations.read_only_hint is False
    assert tools["delete_employee_override"].annotations.destructive_hint is True


def test_update_group_policies_forwards_the_frontend_batch_operation(monkeypatch):
    request = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(server_module, "_request", request)
    context = object()

    result = asyncio.run(
        server_module.update_group_policies(
            context,
            group_id=7,
            add_policy_ids=[11, 13],
            remove_policy_ids=[5],
        )
    )

    assert result == {"ok": True}
    request.assert_awaited_once_with(
        context,
        "PATCH",
        "/groups/7/policies",
        body={"add_policy_ids": [11, 13], "remove_policy_ids": [5]},
    )


def test_update_employee_schema_names_supported_fields_and_rejects_unknown_fields():
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    schema = tools["update_employee"].input_schema
    changes = schema["$defs"]["EmployeeUpdateInput"]

    assert changes["additionalProperties"] is False
    assert set(changes["properties"]) == {
        "name",
        "state",
        "department",
        "employee_type",
        "location",
        "start_date",
        "manager_id",
    }
    assert "first_name" not in changes["properties"]

    with pytest.raises(ToolError, match="first_name") as failure:
        asyncio.run(
            server.call_tool(
                "update_employee",
                {"employee_id": 7, "changes": {"first_name": "Ada"}},
            )
        )
    assert "Extra inputs are not permitted" in str(failure.value)


def test_tool_input_schemas_do_not_publish_opaque_objects():
    def contains_opaque_object(value):
        if isinstance(value, dict):
            if value.get("additionalProperties") is True:
                return True
            return any(contains_opaque_object(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_opaque_object(item) for item in value)
        return False

    tools = asyncio.run(server.list_tools())
    assert not {
        tool.name for tool in tools if contains_opaque_object(tool.input_schema)
    }


def test_structured_backend_error_becomes_actionable_tool_error():
    response = httpx.Response(
        403,
        json={
            "error": {
                "category": "authorization",
                "code": "insufficient_permission",
                "message": "Your roles do not grant the required permission",
                "issues": [
                    {
                        "code": "insufficient_permission",
                        "message": "Your roles do not grant the required permission",
                        "path": ["authorization", "permissions"],
                        "metadata": {
                            "required_permissions": ["employees:update"],
                            "granted_permissions": ["employees:read"],
                        },
                    }
                ],
            }
        },
    )

    message = str(server_module._backend_tool_error(response))

    assert "PolicyOS authorization error" in message
    assert "HTTP 403" in message
    assert "insufficient_permission" in message
    assert "employees:update" in message


def test_expected_backend_tool_error_reaches_the_mcp_client(monkeypatch):
    request = AsyncMock(
        side_effect=ToolError(
            "PolicyOS authorization error (HTTP 403, insufficient_permission): "
            "Your roles do not grant the required permission"
        )
    )
    monkeypatch.setattr(server_module, "_request", request)

    with pytest.raises(ToolError) as failure:
        asyncio.run(
            server.call_tool(
                "update_employee",
                {"employee_id": 7, "changes": {"name": "Ada Lovelace"}},
            )
        )

    message = str(failure.value)
    assert "Error executing tool update_employee" in message
    assert "insufficient_permission" in message
    assert "Your roles do not grant the required permission" in message
    assert "Error executing tool update_employee" != message
    request.assert_awaited_once()
    assert request.await_args.kwargs["body"] == {"name": "Ada Lovelace"}
