import pytest
from fastapi import HTTPException

from app.dates import current_date
from app.models import Policy
from app.services.access_control import PermissionDeniedError
from app.services.auth import AuthenticatedPrincipal
from app.services.policy_access import (
    policy_capabilities,
    require_policy_version_create,
)


def _human(*permissions: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="author@example.com",
        scopes=frozenset(),
        credential_id=None,
        credential_name="human-session",
        authentication_method="human_session",
        user_id=7,
        session_id=9,
        permissions=frozenset(permissions),
    )


def test_policy_capabilities_combine_permission_and_record_state():
    author = _human("policies:version:create")

    draft = policy_capabilities(author, Policy(status="draft"))
    active = policy_capabilities(author, Policy(status="active"))
    archived = policy_capabilities(author, Policy(status="archived"))

    assert draft.can_create_version is True
    assert draft.can_activate is False
    assert draft.can_archive is False
    assert active.can_create_version is False
    assert archived.can_create_version is False


def test_active_policy_version_requires_activation_authority():
    author = _human("policies:version:create")
    administrator = _human(
        "policies:version:create",
        "policies:activate",
        "policies:archive",
    )

    with pytest.raises(PermissionDeniedError):
        require_policy_version_create(author, Policy(status="active"))

    require_policy_version_create(administrator, Policy(status="active"))
    capabilities = policy_capabilities(administrator, Policy(status="active"))
    assert capabilities.can_create_version is True
    assert capabilities.can_archive is True


def test_archived_policy_must_be_reactivated_before_versioning():
    administrator = _human(
        "policies:version:create",
        "policies:activate",
    )

    with pytest.raises(HTTPException) as exc:
        require_policy_version_create(
            administrator,
            Policy(status="archived"),
        )

    assert exc.value.status_code == 409


def test_legacy_policy_update_retains_combined_capabilities():
    capabilities = policy_capabilities(
        _human("policies:update"),
        Policy(status="active"),
    )

    assert capabilities.can_update is True
    assert capabilities.can_create_version is True
    assert capabilities.can_archive is True


def _policy_payload(name: str, field_id: int, *, status: str = "active") -> dict:
    return {
        "name": name,
        "status": status,
        "priority": 10,
        "condition_group": {
            "logical_operator": "and",
            "conditions": [
                {
                    "field": "department",
                    "operator": "=",
                    "value": "Engineering",
                }
            ],
        },
        "values": [
            {
                "assignment_field_definition_id": field_id,
                "value": "enabled",
            }
        ],
    }


def test_it_policy_administrator_is_limited_to_application_access(client):
    root = {
        "name": "Root Admin",
        "email": "root@example.com",
        "password": "root password for testing",
    }
    assert client.post("/auth/setup-root", json=root).status_code == 201
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"

    access = client.post(
        "/assignment-fields",
        json={"name": "Application Access", "cardinality": "many"},
    ).json()
    pay = client.post(
        "/assignment-fields",
        json={"name": "Pay Schedule", "cardinality": "one"},
    ).json()
    access_policy = client.post(
        "/policies",
        json=_policy_payload("Engineering applications", access["id"]),
    ).json()
    pay_policy = client.post(
        "/policies",
        json=_policy_payload("Engineering payroll", pay["id"]),
    ).json()

    role = client.post(
        "/roles",
        json={
            "name": "IT Policy Administrator",
            "employee_scope": "all",
            "assignment_field_scope": "selected",
            "assignment_field_ids": [access["id"]],
            "permissions": [
                "policies:read",
                "policies:create",
                "policies:version:create",
                "policies:activate",
                "policies:archive",
            ],
        },
    ).json()
    assert client.post(
        "/users",
        json={
            "name": "IT Administrator",
            "email": "it@example.com",
            "temporary_password": "temporary password value",
            "role_ids": [role["id"]],
        },
    ).status_code == 201
    assert client.post("/auth/logout").status_code == 204
    assert client.post(
        "/auth/login",
        json={
            "email": "it@example.com",
            "password": "temporary password value",
        },
    ).status_code == 200
    assert client.post(
        "/auth/change-password",
        json={
            "current_password": "temporary password value",
            "new_password": "permanent password value",
        },
    ).status_code == 200

    policies = client.get("/policies")
    assert policies.status_code == 200
    assert [item["id"] for item in policies.json()] == [access_policy["id"]]
    capabilities = policies.json()[0]["capabilities"]
    assert capabilities == {
        "can_update": False,
        "can_create_version": True,
        "can_activate": False,
        "can_archive": True,
    }

    assert client.patch(
        f"/policies/{pay_policy['id']}",
        json={"status": "archived"},
    ).status_code == 404
    assert client.post(
        f"/policies/{pay_policy['id']}/versions",
        json={
            **{
                key: value
                for key, value in _policy_payload("ignored", pay["id"]).items()
                if key not in {"name", "status"}
            },
            "effective_from": current_date().replace(year=current_date().year + 1).isoformat(),
        },
    ).status_code == 404
    archived = client.patch(
        f"/policies/{access_policy['id']}",
        json={"status": "archived"},
    )
    assert archived.status_code == 200
    assert archived.json()["capabilities"] == {
        "can_update": False,
        "can_create_version": False,
        "can_activate": True,
        "can_archive": False,
    }
