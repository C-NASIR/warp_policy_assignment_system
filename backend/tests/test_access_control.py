from app.services.human_auth import SESSION_COOKIE_NAME


ROOT = {
    "name": "Root Admin",
    "email": "root@example.com",
    "password": "root password for testing",
}


def _human(client) -> None:
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"


def _setup_root(client) -> dict:
    response = client.post("/auth/setup-root", json=ROOT)
    assert response.status_code == 201, response.text
    _human(client)
    return response.json()


def _create_role(client, permissions: list[str], name: str = "Employee viewer") -> dict:
    response = client.post(
        "/roles",
        json={
            "name": name,
            "description": "A deliberately limited role",
            "permissions": permissions,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_user(client, role_id: int) -> dict:
    response = client.post(
        "/users",
        json={
            "name": "Morgan Lee",
            "email": "Morgan.Lee@example.com",
            "temporary_password": "temporary password value",
            "role_ids": [role_id],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_root_can_manage_roles_and_users(client):
    root = _setup_root(client)
    assert root["permissions"] == ["*"]

    catalog = client.get("/authorization/permissions")
    assert catalog.status_code == 200
    assert {item["name"] for item in catalog.json()} >= {
        "employees:read",
        "access:manage",
        "changes:execute",
    }

    role = _create_role(client, ["employees:read", "assignments:read"])
    assert role["permissions"] == ["assignments:read", "employees:read"]
    assert role["user_count"] == 0

    user = _create_user(client, role["id"])
    assert user["email"] == "morgan.lee@example.com"
    assert user["password_change_required"] is True
    assert user["roles"] == [{"id": role["id"], "name": role["name"]}]
    assert user["permissions"] == ["assignments:read", "employees:read"]

    assigned_role = client.get(f"/roles/{role['id']}").json()
    assert assigned_role["user_count"] == 1
    cannot_delete = client.delete(f"/roles/{role['id']}")
    assert cannot_delete.status_code == 409


def test_temporary_password_is_forced_and_role_permissions_are_enforced(client):
    _setup_root(client)
    role = _create_role(client, ["employees:read"])
    _create_user(client, role["id"])
    assert client.post("/auth/logout").status_code == 204

    login = client.post(
        "/auth/login",
        json={"email": "morgan.lee@example.com", "password": "temporary password value"},
    )
    assert login.status_code == 200
    assert login.json()["password_change_required"] is True

    forced = client.get("/employees")
    assert forced.status_code == 403
    assert "temporary password" in forced.json()["detail"]

    changed = client.post(
        "/auth/change-password",
        json={
            "current_password": "temporary password value",
            "new_password": "permanent password value",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["password_change_required"] is False

    assert client.get("/employees").status_code == 200
    denied_read = client.get("/policies")
    assert denied_read.status_code == 403
    assert denied_read.json()["error"]["code"] == "insufficient_permission"
    assert denied_read.json()["error"]["issues"][0]["metadata"]["required_permissions"] == ["policies:read"]
    assert client.post(
        "/employees",
        json={
            "name": "Avery Stone",
            "state": "Illinois",
            "department": "Operations",
            "employee_type": "full-time",
        },
    ).status_code == 403


def test_permission_changes_apply_to_existing_sessions(client):
    _setup_root(client)
    role = _create_role(client, ["employees:read"])
    _create_user(client, role["id"])
    root_cookie = client.cookies.get(SESSION_COOKIE_NAME)

    assert client.post(
        "/auth/login",
        json={"email": "morgan.lee@example.com", "password": "temporary password value"},
    ).status_code == 200
    assert client.post(
        "/auth/change-password",
        json={
            "current_password": "temporary password value",
            "new_password": "permanent password value",
        },
    ).status_code == 200
    user_cookie = client.cookies.get(SESSION_COOKIE_NAME)
    employee = {
        "name": "Avery Stone",
        "state": "Illinois",
        "department": "Operations",
        "employee_type": "full-time",
    }
    assert client.post("/employees", json=employee).status_code == 403

    client.cookies.set(SESSION_COOKIE_NAME, root_cookie)
    updated = client.patch(
        f"/roles/{role['id']}",
        json={"permissions": ["employees:read", "employees:create"]},
    )
    assert updated.status_code == 200
    assert updated.json()["permissions"] == ["employees:create", "employees:read"]

    client.cookies.set(SESSION_COOKIE_NAME, user_cookie)
    assert client.post("/employees", json=employee).status_code == 201


def test_disabling_user_revokes_active_sessions(client):
    _setup_root(client)
    role = _create_role(client, ["employees:read"])
    user = _create_user(client, role["id"])

    assert client.post("/auth/logout").status_code == 204
    assert client.post(
        "/auth/login",
        json={"email": "morgan.lee@example.com", "password": "temporary password value"},
    ).status_code == 200
    user_cookie = client.cookies.get(SESSION_COOKIE_NAME)
    assert user_cookie

    assert client.post("/auth/logout").status_code == 204
    assert client.post(
        "/auth/login",
        json={"email": ROOT["email"], "password": ROOT["password"]},
    ).status_code == 200
    disabled = client.delete(f"/users/{user['id']}")
    assert disabled.status_code == 204

    client.cookies.set(SESSION_COOKIE_NAME, user_cookie)
    denied = client.get("/auth/me")
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "session_revoked"


def test_role_and_user_validation(client):
    _setup_root(client)
    unknown_permission = client.post(
        "/roles",
        json={"name": "Invalid", "permissions": ["everything:manage"]},
    )
    assert unknown_permission.status_code == 422

    role = _create_role(client, ["access:read"])
    duplicate = client.post(
        "/roles",
        json={"name": "employee VIEWER", "permissions": []},
    )
    assert duplicate.status_code == 409

    no_role = client.post(
        "/users",
        json={
            "name": "No Access",
            "email": "none@example.com",
            "temporary_password": "temporary password value",
            "role_ids": [],
        },
    )
    assert no_role.status_code == 422

    root_user = client.get("/users").json()[0]
    assert root_user["is_root"] is True
    cannot_disable_root = client.delete(f"/users/{root_user['id']}")
    assert cannot_disable_root.status_code == 409
    assert role["id"] > 0
