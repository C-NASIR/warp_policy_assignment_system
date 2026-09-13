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


def _field(client, name: str, cardinality: str = "one") -> dict:
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": cardinality},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _policy(client, name: str, values: list[dict], *, priority: int = 10) -> dict:
    response = client.post(
        "/policies",
        json={
            "name": name,
            "priority": priority,
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
            "values": values,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login_scoped_user(client) -> None:
    assert client.post("/auth/logout").status_code == 204
    assert client.post(
        "/auth/login",
        json={
            "email": "it-admin@example.com",
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


def test_selected_assignment_fields_filter_reads_and_mutations(client):
    assert client.post("/auth/setup-root", json=ROOT).status_code == 201
    _human(client)
    access = _field(client, "application_access", "many")
    pay = _field(client, "pay_schedule")
    access_policy = _policy(
        client,
        "Engineering applications",
        [
            {
                "assignment_field_definition_id": access["id"],
                "value": "GitHub",
            }
        ],
    )
    pay_policy = _policy(
        client,
        "Engineering payroll",
        [
            {
                "assignment_field_definition_id": pay["id"],
                "value": "biweekly",
            }
        ],
    )
    mixed_policy = _policy(
        client,
        "Mixed domains",
        [
            {
                "assignment_field_definition_id": access["id"],
                "value": "Slack",
            },
            {
                "assignment_field_definition_id": pay["id"],
                "value": "monthly",
            },
        ],
        priority=1,
    )
    employee_response = client.post(
        "/employees",
        json={
            "name": "Alice",
            "state": "IL",
            "department": "Engineering",
            "employee_type": "full-time",
        },
    )
    assert employee_response.status_code == 201, employee_response.text
    employee = employee_response.json()
    group = client.post("/groups", json={"name": "Engineering"}).json()
    assert client.post(
        f"/groups/{group['id']}/policies/{access_policy['id']}"
    ).status_code == 201
    assert client.post(
        f"/groups/{group['id']}/policies/{pay_policy['id']}"
    ).status_code == 201
    pay_override = client.post(
        f"/employees/{employee['id']}/overrides",
        json={
            "assignment_field_definition_id": pay["id"],
            "value": "weekly",
        },
    ).json()

    role_response = client.post(
        "/roles",
        json={
            "name": "IT administrator",
            "employee_scope": "all",
            "assignment_field_scope": "selected",
            "assignment_field_ids": [access["id"]],
            "permissions": [
                "employees:read",
                "policies:read",
                "policies:create",
                "policies:update",
                "groups:read",
                "groups:update",
                "assignments:read",
                "assignments:manage",
                "settings:read",
                "settings:manage",
                "audit:read",
                "changes:preview",
            ],
        },
    )
    assert role_response.status_code == 201, role_response.text
    role = role_response.json()
    assert role["assignment_field_scope"] == "selected"
    assert role["assignment_field_ids"] == [access["id"]]
    user_response = client.post(
        "/users",
        json={
            "name": "IT Admin",
            "email": "it-admin@example.com",
            "temporary_password": "temporary password value",
            "role_ids": [role["id"]],
        },
    )
    assert user_response.status_code == 201, user_response.text
    _login_scoped_user(client)
    scoped_cookie = client.cookies.get(SESSION_COOKIE_NAME)

    fields = client.get("/assignment-fields")
    assert fields.status_code == 200
    assert [item["id"] for item in fields.json()] == [access["id"]]
    assert client.get(f"/assignment-fields/{pay['id']}").status_code == 404
    assert client.post(
        "/assignment-fields",
        json={"name": "device_access", "cardinality": "many"},
    ).status_code == 403

    policies = client.get("/policies")
    assert policies.status_code == 200
    assert [item["id"] for item in policies.json()] == [access_policy["id"]]
    assert client.get(f"/policies/{pay_policy['id']}").status_code == 404
    assert client.get(f"/policies/{mixed_policy['id']}").status_code == 404
    hidden_policy_create = client.post(
        "/policies",
        json={
            "name": "Hidden payroll policy",
            "priority": 20,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "state", "operator": "=", "value": "TX"}
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": pay["id"],
                    "value": "semimonthly",
                }
            ],
        },
    )
    assert hidden_policy_create.status_code == 404
    allowed_policy_create = client.post(
        "/policies",
        json={
            "name": "Texas applications",
            "priority": 20,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "state", "operator": "=", "value": "TX"}
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": access["id"],
                    "value": "Linear",
                }
            ],
        },
    )
    assert allowed_policy_create.status_code == 201, allowed_policy_create.text
    allowed_policy = allowed_policy_create.json()
    hidden_version = client.post(
        f"/policies/{access_policy['id']}/versions",
        json={
            "priority": 20,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "state", "operator": "=", "value": "TX"}
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": pay["id"],
                    "value": "semimonthly",
                }
            ],
        },
    )
    assert hidden_version.status_code == 404

    assignments = client.get(f"/employees/{employee['id']}/assignments").json()
    assert {item["assignment_field_definition_id"] for item in assignments} == {
        access["id"]
    }
    directory_entry = next(
        item
        for item in client.get("/employees").json()
        if item["id"] == employee["id"]
    )
    assert directory_entry["active_assignment_count"] == len(assignments)
    query = client.post(
        "/assignment-queries",
        json={
            "employee_ids": [employee["id"]],
            "evaluation_date": current_date().isoformat(),
        },
    ).json()
    assert {
        item["assignment_field_definition"]["id"]
        for item in query[0]["assignments"]
    } == {access["id"]}
    summary = client.get("/assignment-summary").json()
    assert summary["field_count"] == 1
    assert summary["fields"][0]["assignment_field_definition"]["id"] == access["id"]

    group_policies = client.get(f"/groups/{group['id']}/policies").json()
    assert [item["id"] for item in group_policies] == [access_policy["id"]]
    assert client.delete(
        f"/groups/{group['id']}/policies/{pay_policy['id']}"
    ).status_code == 404
    assert client.post(
        f"/employees/{employee['id']}/overrides",
        json={
            "assignment_field_definition_id": pay["id"],
            "value": "semimonthly",
        },
    ).status_code == 404
    assert client.delete(
        f"/employees/{employee['id']}/overrides/{pay_override['id']}"
    ).status_code == 404
    assert client.post(
        "/change-previews",
        json={
            "type": "policy_version_create",
            "policy_id": pay_policy["id"],
            "version": {
                "priority": 20,
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
                        "assignment_field_definition_id": pay["id"],
                        "value": "semimonthly",
                    }
                ],
            },
        },
    ).status_code == 404

    policy_audits = client.get("/audit-logs?entity_type=Policy&limit=100").json()
    assert {item["entity_id"] for item in policy_audits} == {
        access_policy["id"],
        allowed_policy["id"],
    }
    policy_version_audits = client.get(
        "/audit-logs?entity_type=PolicyVersion&limit=100"
    ).json()
    assert {item["entity_id"] for item in policy_version_audits} == {
        access_policy["versions"][0]["id"],
        allowed_policy["versions"][0]["id"],
    }
    assert client.get(
        "/audit-logs?entity_type=EmployeeOverride&limit=100"
    ).json() == []
    group_audits = client.get(
        f"/audit-logs?entity_type=Group&entity_id={group['id']}&limit=100"
    ).json()
    assert {
        item["action"]
        for item in group_audits
        if item["action"].startswith("policy_")
    } == {"policy_attached"}
    assignment_audits = client.get(
        "/audit-logs?entity_type=EmployeeAssignment&limit=100"
    ).json()
    assert assignment_audits
    assert {
        (item["after"] or item["before"])["assignment_field_definition_id"]
        for item in assignment_audits
    } == {access["id"]}

    assert client.post(
        "/auth/login",
        json={"email": ROOT["email"], "password": ROOT["password"]},
    ).status_code == 200
    changed = client.patch(
        f"/roles/{role['id']}",
        json={
            "assignment_field_scope": "selected",
            "assignment_field_ids": [pay["id"]],
        },
    )
    assert changed.status_code == 200, changed.text
    client.cookies.set(SESSION_COOKIE_NAME, scoped_cookie)
    assert [item["id"] for item in client.get("/assignment-fields").json()] == [
        pay["id"]
    ]
    assert [item["id"] for item in client.get("/policies").json()] == [
        pay_policy["id"]
    ]


def test_assignment_field_grants_union_across_roles(client):
    assert client.post("/auth/setup-root", json=ROOT).status_code == 201
    _human(client)
    access = _field(client, "application_access", "many")
    pay = _field(client, "pay_schedule")
    badge = _field(client, "badge")

    role_ids = []
    for name, field_id in (("IT", access["id"]), ("Payroll", pay["id"])):
        response = client.post(
            "/roles",
            json={
                "name": name,
                "employee_scope": "all",
                "assignment_field_scope": "selected",
                "assignment_field_ids": [field_id],
                "permissions": ["settings:read"],
            },
        )
        assert response.status_code == 201, response.text
        role_ids.append(response.json()["id"])
    assert client.post(
        "/users",
        json={
            "name": "IT Admin",
            "email": "it-admin@example.com",
            "temporary_password": "temporary password value",
            "role_ids": role_ids,
        },
    ).status_code == 201

    _login_scoped_user(client)
    assert {item["id"] for item in client.get("/assignment-fields").json()} == {
        access["id"],
        pay["id"],
    }
    assert badge["id"] not in {
        item["id"] for item in client.get("/assignment-fields").json()
    }
