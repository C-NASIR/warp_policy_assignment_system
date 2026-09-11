from datetime import timedelta

from app.dates import current_datetime


def _issue_credential(
    client,
    *,
    name: str,
    scopes: list[str],
    subject: str = "integration-agent",
    expires_at: str | None = None,
) -> dict:
    payload = {
        "name": name,
        "subject": subject,
        "scopes": scopes,
    }
    if expires_at is not None:
        payload["expires_at"] = expires_at
    response = client.post("/auth/credentials", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_is_public_but_business_endpoints_require_authentication(client):
    health = client.get("/", headers={"Authorization": ""})
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "service": "policy-assignment-system",
        "database": "ready",
    }

    missing = client.get("/employees", headers={"Authorization": ""})
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert missing.json()["error"] == {
        "category": "authentication",
        "code": "authentication_required",
        "message": "Authentication is required",
        "issues": [
            {
                "code": "authentication_required",
                "message": "Authentication is required",
                "path": ["authorization"],
                "metadata": {},
            }
        ],
    }

    invalid = client.get(
        "/employees",
        headers=_authorization("wpa_invalid-credential"),
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "invalid_credential"


def test_credential_is_returned_once_stored_hashed_and_can_be_revoked(client, db):
    created = _issue_credential(
        client,
        name="frontend-readonly",
        subject="frontend-user",
        scopes=["read"],
        expires_at=(current_datetime() + timedelta(days=7)).isoformat(),
    )
    assert created["token"].startswith("wpa_")
    assert created["token_prefix"] == created["token"][:12]

    listed = client.get("/auth/credentials")
    assert listed.status_code == 200
    assert listed.json() == [{key: value for key, value in created.items() if key != "token"}]
    assert "token_hash" not in listed.text
    assert created["token"] not in listed.text

    credential_audits = client.get(
        "/audit-logs",
        params={"entity_type": "APICredential", "entity_id": created["id"]},
    ).json()
    assert credential_audits[0]["action"] == "created"
    assert "token_hash" not in credential_audits[0]["after"]
    assert "token" not in credential_audits[0]["after"]

    from app.models import APICredential

    stored = db.get(APICredential, created["id"])
    assert stored is not None
    assert stored.token_hash != created["token"]
    assert len(stored.token_hash) == 64

    assert client.get(
        "/employees",
        headers=_authorization(created["token"]),
    ).status_code == 200
    assert client.delete(f"/auth/credentials/{created['id']}").status_code == 204

    revoked = client.get(
        "/employees",
        headers=_authorization(created["token"]),
    )
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "credential_revoked"


def test_operation_scopes_enforce_read_preview_execute_and_audit_boundaries(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "CHANGE_APPROVAL_SECRET",
        "test-change-approval-secret-with-at-least-32-bytes",
    )
    read_credential = _issue_credential(
        client,
        name="reader",
        scopes=["read"],
    )
    read_headers = _authorization(read_credential["token"])
    assert client.get("/employees", headers=read_headers).status_code == 200

    denied = client.post(
        "/employees",
        headers=read_headers,
        json={
            "name": "Alice",
            "state": "California",
            "department": "Engineering",
            "employee_type": "regular",
        },
    )
    assert denied.status_code == 403
    issue = denied.json()["error"]["issues"][0]
    assert issue["metadata"] == {
        "required_scopes": ["execute"],
        "granted_scopes": ["read"],
    }

    preview_credential = _issue_credential(
        client,
        name="previewer",
        scopes=["preview"],
    )
    preview_headers = _authorization(preview_credential["token"])
    preview = client.post(
        "/change-previews",
        headers=preview_headers,
        json={
            "type": "employee_create",
            "employee": {
                "name": "Preview Alice",
                "state": "California",
                "department": "Engineering",
                "employee_type": "regular",
            },
        },
    )
    assert preview.status_code == 200
    assert client.post(
        "/change-executions",
        headers=preview_headers,
        json={
            "change": {
                "type": "employee_create",
                "employee": {
                    "name": "Preview Alice",
                    "state": "California",
                    "department": "Engineering",
                    "employee_type": "regular",
                },
            },
            "approval_token": preview.json()["approval"]["token"],
        },
    ).status_code == 403
    assert client.get("/audit-logs", headers=read_headers).status_code == 403


def test_mutation_actor_comes_from_subject_and_override_requires_scope(client):
    executor = _issue_credential(
        client,
        name="mcp-executor",
        subject="mcp-agent",
        scopes=["execute"],
    )
    headers = _authorization(executor["token"])
    created = client.post(
        "/employees",
        headers=headers,
        json={
            "name": "Alice",
            "state": "California",
            "department": "Engineering",
            "employee_type": "regular",
        },
    )
    assert created.status_code == 201
    audit = client.get(
        "/audit-logs",
        params={"entity_type": "Employee", "entity_id": created.json()["id"]},
    ).json()
    assert audit[0]["actor"] == "mcp-agent"

    denied = client.post(
        "/employees",
        headers={**headers, "X-Actor": "human-admin"},
        json={
            "name": "Bob",
            "state": "Wisconsin",
            "department": "Sales",
            "employee_type": "regular",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["issues"][0]["metadata"]["required_scopes"] == [
        "actor:override"
    ]

    delegated = _issue_credential(
        client,
        name="delegated-executor",
        subject="trusted-gateway",
        scopes=["execute", "actor:override"],
    )
    delegated_response = client.post(
        "/employees",
        headers={
            **_authorization(delegated["token"]),
            "X-Actor": "human-admin",
        },
        json={
            "name": "Bob",
            "state": "Wisconsin",
            "department": "Sales",
            "employee_type": "regular",
        },
    )
    assert delegated_response.status_code == 201
    delegated_audit = client.get(
        "/audit-logs",
        params={
            "entity_type": "Employee",
            "entity_id": delegated_response.json()["id"],
        },
    ).json()
    assert delegated_audit[0]["actor"] == "human-admin"


def test_credential_validation_and_scope_catalog_are_structured(client):
    catalog = client.get("/auth/scopes")
    assert catalog.status_code == 200
    assert {item["name"] for item in catalog.json()} == {
        "read",
        "preview",
        "execute",
        "audit",
        "credentials:manage",
        "actor:override",
    }

    invalid = client.post(
        "/auth/credentials",
        json={
            "name": "invalid",
            "subject": "agent",
            "scopes": ["root"],
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["category"] == "validation"
    assert invalid.json()["error"]["code"] == "unknown_operation_scope"
    assert invalid.json()["error"]["issues"][0]["metadata"] == {
        "unknown_scopes": ["root"]
    }

    _issue_credential(client, name="unique-name", scopes=["read"])
    duplicate = client.post(
        "/auth/credentials",
        json={
            "name": "unique-name",
            "subject": "another-agent",
            "scopes": ["read"],
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "credential_name_conflict"

    expired = client.post(
        "/auth/credentials",
        json={
            "name": "already-expired",
            "subject": "agent",
            "scopes": ["read"],
            "expires_at": (current_datetime() - timedelta(seconds=1)).isoformat(),
        },
    )
    assert expired.status_code == 422
    assert expired.json()["error"]["code"] == "credential_expiry_not_future"


def test_openapi_documents_bearer_auth_and_required_operation_scopes(client):
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/"]["get"].get("security") is None
    assert schema["paths"]["/employees"]["post"]["x-required-scopes"] == ["execute"]
    assert schema["paths"]["/change-previews"]["post"]["x-required-scopes"] == [
        "preview"
    ]
    assert schema["paths"]["/audit-logs"]["get"]["x-required-scopes"] == ["audit"]
    assert schema["paths"]["/auth/credentials"]["post"]["x-required-scopes"] == [
        "credentials:manage"
    ]
