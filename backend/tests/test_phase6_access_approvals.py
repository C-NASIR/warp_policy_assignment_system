from datetime import timedelta

from app.dates import current_date
from app.services.human_auth import SESSION_COOKIE_NAME

APPROVAL_SECRET = "0123456789abcdef0123456789abcdef"
ROOT = {
    "name": "Root Admin",
    "email": "root@example.com",
    "password": "root password for testing",
}


def _role(
    client,
    name: str,
    permissions: list[str],
    *,
    automation_eligible: bool = False,
) -> dict:
    response = client.post(
        "/roles",
        json={
            "name": name,
            "permissions": permissions,
            "employee_scope": "all",
            "assignment_field_scope": "all",
            "automation_eligible": automation_eligible,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _user(
    client,
    name: str,
    email: str,
    role_id: int,
    *,
    employee_id: int | None = None,
) -> dict:
    response = client.post(
        "/users",
        json={
            "name": name,
            "email": email,
            "temporary_password": "temporary password value",
            "role_ids": [role_id],
            "employee_id": employee_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client, email: str) -> None:
    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "temporary password value",
        },
    )
    assert response.status_code == 200, response.text
    changed = client.post(
        "/auth/change-password",
        json={
            "current_password": "temporary password value",
            "new_password": "permanent password value",
        },
    )
    assert changed.status_code == 200, changed.text


def _policy_version(role_id: int) -> dict:
    return {
        "priority": 20,
        "effective_from": current_date().isoformat(),
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
        "values": [],
        "automated_role_ids": [role_id],
    }


def test_human_approval_executes_previewed_automated_access_change(
    client,
    monkeypatch,
):
    monkeypatch.setenv("CHANGE_APPROVAL_SECRET", APPROVAL_SECRET)
    assert client.post("/auth/setup-root", json=ROOT).status_code == 201
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"
    root_cookie = client.cookies.get(SESSION_COOKIE_NAME)

    baseline = _role(client, "Employee baseline", ["employees:read"])
    automated = _role(
        client,
        "Engineering auditor",
        ["audit:read"],
        automation_eligible=True,
    )
    author_role = _role(
        client,
        "Policy author",
        [
            "policies:read",
            "policies:create",
            "policies:version:create",
            "policies:activate",
            "changes:preview",
            "changes:approve",
        ],
    )
    approver_role = _role(
        client,
        "Policy approver",
        [
            "policies:read",
            "policies:version:create",
            "policies:activate",
            "changes:approve",
            "changes:execute",
        ],
    )
    employee = client.post(
        "/employees",
        json={
            "name": "Avery Engineer",
            "state": "Illinois",
            "department": "Engineering",
            "employee_type": "full-time",
        },
    ).json()
    target = _user(
        client,
        "Avery Engineer",
        "avery@example.com",
        baseline["id"],
        employee_id=employee["id"],
    )
    _user(client, "Policy Author", "author@example.com", author_role["id"])
    _user(client, "Policy Approver", "approver@example.com", approver_role["id"])
    policy_response = client.post(
        "/policies",
        json={
            "name": "Engineering access",
            "status": "active",
            "priority": 10,
            "effective_from": (current_date() - timedelta(days=1)).isoformat(),
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
            "values": [],
        },
    )
    assert policy_response.status_code == 201, policy_response.text
    policy = policy_response.json()

    _login(client, "author@example.com")
    change = {
        "type": "policy_version_create",
        "policy_id": policy["id"],
        "version": _policy_version(automated["id"]),
    }
    preview_response = client.post("/change-previews", json=change)
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["approval"] is None
    assert preview["approval_request_id"]
    assert preview["affected_user_count"] == 1
    assert preview["access_changes"] == [
        {
            "user_id": target["id"],
            "employee_id": employee["id"],
            "employee_name": "Avery Engineer",
            "role_id": automated["id"],
            "role_name": "Engineering auditor",
            "action": "grant",
            "source_policy_version_id": None,
            "source_is_proposed": True,
        }
    ]
    request_id = preview["approval_request_id"]
    self_approval = client.post(f"/approval-requests/{request_id}/approve")
    assert self_approval.status_code == 409
    assert "own changes" in self_approval.json()["detail"]

    _login(client, "approver@example.com")
    pending = client.get("/approval-requests").json()
    assert pending[0]["id"] == request_id
    assert pending[0]["can_approve"] is True
    approved = client.post(f"/approval-requests/{request_id}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["can_execute"] is True

    executed = client.post(
        "/change-executions",
        json={"approval_request_id": request_id},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "executed"
    assert executed.json()["affected_user_count"] == 1

    client.cookies.set(SESSION_COOKIE_NAME, root_cookie)
    policy_after = client.get(f"/policies/{policy['id']}").json()
    assert policy_after["versions"][-1]["created_by"] == "author@example.com"
    target_after = client.get(f"/users/{target['id']}").json()
    assert target_after["roles"] == [
        {"id": baseline["id"], "name": "Employee baseline"}
    ]
    assert target_after["automated_roles"] == [
        {"id": automated["id"], "name": "Engineering auditor"}
    ]
    assert set(target_after["permissions"]) == {"employees:read", "audit:read"}

    protected = client.patch(
        f"/users/{target['id']}",
        json={"role_ids": [baseline["id"], automated["id"]]},
    )
    assert protected.status_code == 200, protected.text

    moved = client.patch(
        f"/employees/{employee['id']}",
        json={"department": "Sales"},
    )
    assert moved.status_code == 200, moved.text
    target_after_move = client.get(f"/users/{target['id']}").json()
    assert {role["id"] for role in target_after_move["roles"]} == {
        baseline["id"],
        automated["id"],
    }
    assert target_after_move["automated_roles"] == []
    assert set(target_after_move["permissions"]) == {"employees:read", "audit:read"}


def test_automated_policy_requires_safe_role_and_distinct_activator(
    client,
    monkeypatch,
):
    monkeypatch.setenv("CHANGE_APPROVAL_SECRET", APPROVAL_SECRET)
    assert client.post("/auth/setup-root", json=ROOT).status_code == 201
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"

    privileged = client.post(
        "/roles",
        json={
            "name": "Privileged automation",
            "permissions": ["access:manage"],
            "automation_eligible": True,
        },
    )
    assert privileged.status_code == 422
    root_named = client.post(
        "/roles",
        json={
            "name": "Root",
            "permissions": ["employees:read"],
            "automation_eligible": True,
        },
    )
    assert root_named.status_code == 422

    automated = _role(
        client,
        "Provisioned viewer",
        ["employees:read"],
        automation_eligible=True,
    )
    author_role = _role(
        client,
        "Access policy author",
        [
            "policies:create",
            "policies:activate",
            "changes:preview",
            "changes:approve",
        ],
    )
    approver_role = _role(
        client,
        "Access policy activator",
        [
            "policies:read",
            "policies:activate",
            "changes:approve",
            "changes:execute",
        ],
    )
    _user(client, "Author", "author@example.com", author_role["id"])
    _user(client, "Approver", "approver@example.com", approver_role["id"])

    _login(client, "author@example.com")
    created = client.post(
        "/policies",
        json={
            "name": "Employee viewer access",
            "status": "draft",
            **_policy_version(automated["id"]),
        },
    )
    assert created.status_code == 201, created.text
    policy = created.json()
    assert policy["created_by"] == "author@example.com"
    assert policy["versions"][0]["automated_role_ids"] == [automated["id"]]
    self_activation = client.patch(
        f"/policies/{policy['id']}",
        json={"status": "active"},
    )
    assert self_activation.status_code == 409
    preview = client.post(
        "/change-previews",
        json={
            "type": "policy_status_change",
            "policy_id": policy["id"],
            "status": "active",
        },
    )
    assert preview.status_code == 200, preview.text
    request_id = preview.json()["approval_request_id"]
    assert request_id

    _login(client, "approver@example.com")
    assert client.post(
        f"/approval-requests/{request_id}/approve"
    ).status_code == 200
    activated = client.post(
        "/change-executions",
        json={"approval_request_id": request_id},
    )
    assert activated.status_code == 200, activated.text
    policy_after = client.get(f"/policies/{policy['id']}")
    assert policy_after.status_code == 200
    assert policy_after.json()["status"] == "active"
