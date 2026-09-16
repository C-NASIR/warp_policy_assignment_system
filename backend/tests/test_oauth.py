import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.models import OAuthToken
from app.services.human_auth import SESSION_COOKIE_NAME

ROOT = {
    "name": "Root User",
    "email": "root@example.com",
    "password": "correct horse battery staple",
}


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _register(client) -> dict:
    response = client.post(
        "/oauth/register",
        json={
            "client_name": "MCP test client",
            "redirect_uris": ["http://127.0.0.1:8765/callback"],
            "token_endpoint_auth_method": "none",
            "application_type": "native",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["application_type"] == "native"
    return response.json()


def _authorize(client, registered: dict) -> tuple[str, str]:
    verifier, challenge = _pkce()
    payload = {
        "client_id": registered["client_id"],
        "redirect_uri": registered["redirect_uris"][0],
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": "policyos",
        "state": "test-state",
        "resource": "http://127.0.0.1:8001/mcp",
    }
    details = client.get("/oauth/authorize", params=payload)
    assert details.status_code == 200, details.text
    assert details.json()["client_name"] == "MCP test client"
    approved = client.post("/oauth/authorize", json={**payload, "approve": True})
    assert approved.status_code == 200, approved.text
    parsed = urlparse(approved.json()["redirect_uri"])
    query = parse_qs(parsed.query)
    assert query["state"] == ["test-state"]
    assert query["iss"] == ["http://127.0.0.1:8000"]
    return query["code"][0], verifier


def _exchange(client, registered: dict, code: str, verifier: str) -> dict:
    response = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": registered["client_id"],
            "code": code,
            "redirect_uri": registered["redirect_uris"][0],
            "code_verifier": verifier,
            "resource": "http://127.0.0.1:8001/mcp",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _start_root_session(client) -> None:
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"
    response = client.post("/auth/setup-root", json=ROOT)
    assert response.status_code == 201, response.text


def test_oauth_pkce_tokens_are_user_bound_hashed_rotatable_and_revocable(client, db):
    registered = _register(client)
    _start_root_session(client)
    code, verifier = _authorize(client, registered)

    wrong = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": registered["client_id"],
            "code": code,
            "redirect_uri": registered["redirect_uris"][0],
            "code_verifier": "x" * 43,
        },
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"] == "invalid_grant"

    # A failed verifier does not consume the one-time code.
    tokens = _exchange(client, registered, code, verifier)
    assert tokens["access_token"].startswith("poa_")
    assert tokens["refresh_token"].startswith("por_")

    stored = db.scalar(select(OAuthToken))
    assert stored is not None
    assert stored.access_token_hash != tokens["access_token"]
    assert stored.refresh_token_hash != tokens["refresh_token"]

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    userinfo = client.get("/oauth/userinfo", headers=headers)
    assert userinfo.status_code == 200
    assert userinfo.json()["sub"] == ROOT["email"]
    assert client.get("/employees", headers=headers).status_code == 200

    refreshed = client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": registered["client_id"],
            "refresh_token": tokens["refresh_token"],
        },
    )
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    assert client.get("/employees", headers=headers).status_code == 401

    assert client.post("/oauth/revoke", data={"token": new_tokens["access_token"]}).status_code == 200
    revoked = client.get(
        "/employees",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert revoked.status_code == 401


def test_oauth_denial_returns_one_terminal_access_denied_callback(client):
    registered = _register(client)
    _start_root_session(client)
    _, challenge = _pkce()
    payload = {
        "client_id": registered["client_id"],
        "redirect_uri": registered["redirect_uris"][0],
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": "policyos",
        "state": "denial-state",
        "resource": "http://127.0.0.1:8001/mcp",
        "approve": False,
    }

    response = client.post("/oauth/authorize", json=payload)

    assert response.status_code == 200, response.text
    callback = urlparse(response.json()["redirect_uri"])
    assert callback.path == "/callback"
    assert parse_qs(callback.query) == {
        "error": ["access_denied"],
        "error_description": ["The user denied access"],
        "state": ["denial-state"],
        "iss": ["http://127.0.0.1:8000"],
    }


def test_oauth_user_has_the_same_employee_visibility_as_the_browser(client):
    _start_root_session(client)
    own_employee = client.post(
        "/employees",
        json={
            "name": "Alice Agent",
            "state": "IL",
            "department": "Operations",
            "employee_type": "regular",
        },
    ).json()
    client.post(
        "/employees",
        json={
            "name": "Hidden Employee",
            "state": "WI",
            "department": "Finance",
            "employee_type": "regular",
        },
    )
    role = client.post(
        "/roles",
        json={
            "name": "Self service",
            "permissions": ["employees:read"],
            "employee_scope": "self",
            "assignment_field_scope": "none",
        },
    ).json()
    temporary_password = "temporary agent password"
    permanent_password = "permanent agent password"
    created_user = client.post(
        "/users",
        json={
            "name": "Alice Agent",
            "email": "alice@example.com",
            "temporary_password": temporary_password,
            "role_ids": [role["id"]],
            "employee_id": own_employee["id"],
        },
    )
    assert created_user.status_code == 201, created_user.text

    client.cookies.clear()
    login = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": temporary_password},
    )
    assert login.status_code == 200
    changed = client.post(
        "/auth/change-password",
        json={
            "current_password": temporary_password,
            "new_password": permanent_password,
        },
    )
    assert changed.status_code == 200, changed.text

    browser_ids = {item["id"] for item in client.get("/employees").json()}
    assert browser_ids == {own_employee["id"]}

    registered = _register(client)
    code, verifier = _authorize(client, registered)
    tokens = _exchange(client, registered, code, verifier)
    oauth_ids = {
        item["id"]
        for item in client.get(
            "/employees",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        ).json()
    }
    assert oauth_ids == browser_ids


def test_dynamic_registration_rejects_untrusted_http_redirects(client):
    response = client.post(
        "/oauth/register",
        json={
            "client_name": "Unsafe client",
            "redirect_uris": ["http://example.com/callback"],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


def test_oauth_metadata_advertises_client_neutral_mcp_capabilities(client):
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert metadata["token_endpoint_auth_methods_supported"] == ["none"]
    assert metadata["registration_endpoint"].endswith("/oauth/register")
    assert metadata["authorization_endpoint"] == (
        "http://127.0.0.1:8000/oauth/authorize/start"
    )
    assert metadata["client_id_metadata_document_supported"] is True
    assert metadata["authorization_response_iss_parameter_supported"] is True
    assert "scopes_supported" not in metadata


def test_issuer_authorization_endpoint_launches_browser_ui(client):
    response = client.get(
        "/oauth/authorize/start",
        params={
            "client_id": "test-client",
            "redirect_uri": "http://127.0.0.1:8765/callback",
            "response_type": "code",
            "state": "state with spaces",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("http://localhost:3000/oauth/authorize?")
    query = parse_qs(urlparse(location).query)
    assert query == {
        "client_id": ["test-client"],
        "redirect_uri": ["http://127.0.0.1:8765/callback"],
        "response_type": ["code"],
        "state": ["state with spaces"],
    }
    assert response.headers["cache-control"] == "no-store"


def test_client_id_metadata_document_can_register_current_mcp_client(
    client, monkeypatch
):
    client_id = "https://agent.example/client.json"
    monkeypatch.setattr(
        "app.services.oauth._fetch_client_metadata_document",
        lambda value: {
            "client_id": value,
            "client_name": "Portable MCP client",
            "redirect_uris": ["http://127.0.0.1:9876/callback"],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
    )
    _start_root_session(client)
    _, challenge = _pkce()
    response = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": "http://127.0.0.1:9876/callback",
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "policyos",
            "resource": "http://127.0.0.1:8001/mcp",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["client_name"] == "Portable MCP client"


def test_client_id_metadata_document_allows_ephemeral_loopback_port(
    client, monkeypatch
):
    client_id = "https://agent.example/client.json"
    monkeypatch.setattr(
        "app.services.oauth._fetch_client_metadata_document",
        lambda value: {
            "client_id": value,
            "client_name": "Native MCP client",
            "application_type": "native",
            "redirect_uris": [
                "http://127.0.0.1/callback",
                "http://localhost/callback",
            ],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
    )
    _start_root_session(client)

    for redirect_uri in (
        "http://127.0.0.1:49152/callback",
        "http://localhost:49153/callback",
    ):
        _, challenge = _pkce()
        response = client.get(
            "/oauth/authorize",
            params={
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "scope": "policyos",
                "resource": "http://127.0.0.1:8001/mcp",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["redirect_uri"] == redirect_uri


def test_loopback_redirect_port_exception_does_not_allow_other_uri_changes(
    client, monkeypatch
):
    client_id = "https://agent.example/client.json"
    monkeypatch.setattr(
        "app.services.oauth._fetch_client_metadata_document",
        lambda value: {
            "client_id": value,
            "client_name": "Native MCP client",
            "application_type": "native",
            "redirect_uris": ["http://127.0.0.1/callback?channel=codex"],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
    )
    _start_root_session(client)
    _, challenge = _pkce()
    common = {
        "client_id": client_id,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }

    for redirect_uri in (
        "http://127.0.0.1:49152/other?channel=codex",
        "http://127.0.0.1:49152/callback?channel=other",
        "http://localhost:49152/callback?channel=codex",
        "https://127.0.0.1:49152/callback?channel=codex",
    ):
        response = client.get(
            "/oauth/authorize",
            params={**common, "redirect_uri": redirect_uri},
        )
        assert response.status_code == 400
        assert response.json()["error_description"] == (
            "The redirect URI is not registered"
        )


def test_client_id_metadata_document_must_match_its_url(client, monkeypatch):
    client_id = "https://agent.example/client.json"
    monkeypatch.setattr(
        "app.services.oauth._fetch_client_metadata_document",
        lambda _: {
            "client_id": "https://attacker.example/client.json",
            "client_name": "Wrong client",
            "redirect_uris": ["https://attacker.example/callback"],
        },
    )
    _start_root_session(client)
    _, challenge = _pkce()
    response = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": "https://attacker.example/callback",
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_client_metadata"
