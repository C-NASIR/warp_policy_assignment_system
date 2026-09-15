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
            "client_name": "Codex test client",
            "redirect_uris": ["http://127.0.0.1:8765/callback"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert response.status_code == 201, response.text
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
    assert details.json()["client_name"] == "Codex test client"
    approved = client.post("/oauth/authorize", json={**payload, "approve": True})
    assert approved.status_code == 200, approved.text
    parsed = urlparse(approved.json()["redirect_uri"])
    query = parse_qs(parsed.query)
    assert query["state"] == ["test-state"]
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


def test_oauth_metadata_advertises_pkce_and_dynamic_registration(client):
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert metadata["token_endpoint_auth_methods_supported"] == ["none"]
    assert metadata["registration_endpoint"].endswith("/oauth/register")
