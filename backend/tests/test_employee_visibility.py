from app.dates import current_date
from app.services.human_auth import SESSION_COOKIE_NAME

ROOT = {
    "name": "Root Admin",
    "email": "root@example.com",
    "password": "root password for testing",
}


def _human(client) -> None:
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"


def _employee(client, name: str, manager_id: int | None = None) -> dict:
    response = client.post(
        "/employees",
        json={
            "name": name,
            "state": "Illinois",
            "department": "Operations",
            "employee_type": "full-time",
            "manager_id": manager_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _provision_scoped_user(client, employee_id: int, scope: str) -> tuple[dict, dict]:
    role_response = client.post(
        "/roles",
        json={
            "name": f"{scope} manager",
            "employee_scope": scope,
            "permissions": [
                "employees:read",
                "employees:create",
                "employees:update",
                "assignments:read",
                "assignments:manage",
                "groups:read",
                "groups:update",
                "audit:read",
                "changes:preview",
            ],
        },
    )
    assert role_response.status_code == 201, role_response.text
    role = role_response.json()
    user_response = client.post(
        "/users",
        json={
            "name": "Morgan Manager",
            "email": "manager@example.com",
            "temporary_password": "temporary password value",
            "role_ids": [role["id"]],
            "employee_id": employee_id,
        },
    )
    assert user_response.status_code == 201, user_response.text
    return role, user_response.json()


def _login_scoped_user(client) -> None:
    assert client.post("/auth/logout").status_code == 204
    assert client.post(
        "/auth/login",
        json={
            "email": "manager@example.com",
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


def _login_root(client) -> None:
    assert client.post(
        "/auth/login",
        json={"email": ROOT["email"], "password": ROOT["password"]},
    ).status_code == 200


def test_reporting_tree_scope_filters_every_employee_boundary(client):
    assert client.post("/auth/setup-root", json=ROOT).status_code == 201
    _human(client)
    chief = _employee(client, "Chief")
    manager = _employee(client, "Manager", chief["id"])
    report = _employee(client, "Direct Report", manager["id"])
    grandchild = _employee(client, "Indirect Report", report["id"])
    peer = _employee(client, "Peer Manager", chief["id"])

    group = client.post("/groups", json={"name": "Mixed team"}).json()
    assert client.post(f"/groups/{group['id']}/employees/{report['id']}").status_code == 201
    assert client.post(f"/groups/{group['id']}/employees/{peer['id']}").status_code == 201
    _provision_scoped_user(client, manager["id"], "reporting_tree")
    _login_scoped_user(client)

    visible = client.get("/employees")
    assert visible.status_code == 200
    assert visible.headers["x-total-count"] == "3"
    assert {employee["id"] for employee in visible.json()} == {
        manager["id"],
        report["id"],
        grandchild["id"],
    }
    candidates = client.get("/employees/manager-candidates")
    assert candidates.status_code == 200
    assert {item["id"] for item in candidates.json()} == {
        manager["id"],
        report["id"],
        grandchild["id"],
    }
    assert all(set(item) == {"id", "label"} for item in candidates.json())
    assert client.get(f"/employees/{peer['id']}").status_code == 404
    assert client.patch(
        f"/employees/{peer['id']}",
        json={"department": "Finance"},
    ).status_code == 404
    assert client.post(
        "/change-previews",
        json={
            "type": "employee_update",
            "employee_id": peer["id"],
            "changes": {"department": "Finance"},
        },
    ).status_code == 404

    members = client.get(f"/groups/{group['id']}/employees")
    assert members.status_code == 200
    assert [employee["id"] for employee in members.json()] == [report["id"]]
    assert client.post(
        "/assignment-queries",
        json={
            "employee_ids": [manager["id"], report["id"]],
            "evaluation_date": current_date().isoformat(),
        },
    ).status_code == 200
    assert client.post(
        "/assignment-queries",
        json={
            "employee_ids": [peer["id"]],
            "evaluation_date": current_date().isoformat(),
        },
    ).status_code == 404
    summary = client.get("/assignment-summary")
    assert summary.status_code == 200
    assert summary.json()["employee_count"] == 3

    scoped_audit = client.get("/audit-logs?entity_type=Employee&limit=100")
    assert scoped_audit.status_code == 200
    assert {event["entity_id"] for event in scoped_audit.json()} == {
        manager["id"],
        report["id"],
        grandchild["id"],
    }

    created = _employee(client, "New Report", report["id"])
    assert created["manager_id"] == report["id"]
    top_level = client.post(
        "/employees",
        json={
            "name": "Out of tree",
            "state": "Illinois",
            "department": "Operations",
            "employee_type": "full-time",
        },
    )
    assert top_level.status_code == 403

    _login_root(client)
    assert len(client.get("/employees").json()) == 6


def test_scope_changes_apply_to_an_existing_session(client):
    assert client.post("/auth/setup-root", json=ROOT).status_code == 201
    _human(client)
    manager = _employee(client, "Manager")
    report = _employee(client, "Report", manager["id"])
    role, _ = _provision_scoped_user(client, manager["id"], "self")
    _login_scoped_user(client)
    user_cookie = client.cookies.get(SESSION_COOKIE_NAME)

    assert [item["id"] for item in client.get("/employees").json()] == [manager["id"]]
    assert client.post(
        "/employees",
        json={
            "name": "Not visible to self",
            "state": "Illinois",
            "department": "Operations",
            "employee_type": "full-time",
            "manager_id": manager["id"],
        },
    ).status_code == 403

    _login_root(client)
    changed = client.patch(
        f"/roles/{role['id']}",
        json={"employee_scope": "reporting_tree"},
    )
    assert changed.status_code == 200
    assert changed.json()["employee_scope"] == "reporting_tree"

    client.cookies.set(SESSION_COOKIE_NAME, user_cookie)
    assert {item["id"] for item in client.get("/employees").json()} == {
        manager["id"],
        report["id"],
    }
