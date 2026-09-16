import asyncio

from starlette.testclient import TestClient

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


def test_tool_catalog_is_curated_and_marks_mutations():
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    assert {
        "search_employees",
        "get_employee_assignments",
        "query_assignments",
        "list_policies",
        "preview_change",
        "create_employee",
        "create_policy",
        "create_policy_version",
    } <= set(tools)
    assert tools["search_employees"].annotations is not None
    assert tools["preview_change"].annotations is not None
    assert tools["create_employee"].annotations is not None
    assert tools["search_employees"].annotations.read_only_hint is True
    assert tools["preview_change"].annotations.read_only_hint is True
    assert tools["create_employee"].annotations.read_only_hint is False
