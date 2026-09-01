from datetime import timedelta

from app.dates import current_date


def _assignment_field(client, name="pay_schedule", cardinality="one"):
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": cardinality},
    )
    assert response.status_code == 201
    return response.json()


def _condition(field="state", value="California"):
    return {
        "logical_operator": "and",
        "conditions": [{"field": field, "operator": "=", "value": value}],
    }


def _policy(
    client,
    assignment_field_id,
    *,
    condition_field="state",
    condition_value="California",
    value="weekly",
    effective_from=None,
    priority=10,
):
    body = {
        "name": f"{condition_value} {value}",
        "priority": priority,
        "condition_group": _condition(condition_field, condition_value),
        "values": [
            {
                "assignment_field_definition_id": assignment_field_id,
                "value": value,
            }
        ],
    }
    if effective_from is not None:
        body["effective_from"] = effective_from.isoformat()
    response = client.post("/policies", json=body)
    assert response.status_code == 201
    return response.json()


def _employee(client, name="Alice", state="California"):
    response = client.post(
        "/employees",
        json={
            "name": name,
            "state": state,
            "department": "Engineering",
            "employee_type": "regular",
        },
    )
    assert response.status_code == 201
    return response.json()


def _preview(client, body):
    response = client.post("/change-previews", json=body)
    assert response.status_code == 200
    return response.json()


def test_employee_create_and_update_previews_do_not_persist(client):
    field = _assignment_field(client)
    _policy(client, field["id"])

    create_preview = _preview(
        client,
        {
            "type": "employee_create",
            "employee": {
                "name": "Alice",
                "state": "California",
                "department": "Engineering",
                "employee_type": "regular",
            },
        },
    )
    assert create_preview["valid"] is True
    assert create_preview["affected_employee_count"] == 1
    assert create_preview["changes"][0]["employee_id"] is None
    assert [item["value"] for item in create_preview["changes"][0]["added"]] == [
        "weekly"
    ]
    assert client.get("/employees").json() == []

    alice = _employee(client)
    update_preview = _preview(
        client,
        {
            "type": "employee_update",
            "employee_id": alice["id"],
            "changes": {"state": "Texas"},
        },
    )
    change = update_preview["changes"][0]
    assert [item["value"] for item in change["before"]] == ["weekly"]
    assert change["after"] == []
    assert [item["value"] for item in change["removed"]] == ["weekly"]
    assert client.get(f"/employees/{alice['id']}").json()["state"] == "California"
    assert [
        item["value"]
        for item in client.get(f"/employees/{alice['id']}/assignments").json()
    ] == ["weekly"]

    override_response = client.post(
        f"/employees/{alice['id']}/overrides",
        json={
            "assignment_field_definition_id": pay_field["id"],
            "value": "monthly",
        },
    )
    assert override_response.status_code == 201
    override = override_response.json()

    update_preview = _preview(
        client,
        {
            "type": "employee_override_change",
            "action": "update",
            "employee_id": alice["id"],
            "override_id": override["id"],
            "value": "semi-monthly",
        },
    )
    update_change = update_preview["changes"][0]
    assert [item["value"] for item in update_change["before"]] == ["monthly"]
    assert [item["value"] for item in update_change["after"]] == ["semi-monthly"]
    assert update_change["after"][0]["source_id"] is None
    assert update_change["after"][0]["source_is_proposed"] is True

    delete_preview = _preview(
        client,
        {
            "type": "employee_override_change",
            "action": "delete",
            "employee_id": alice["id"],
            "override_id": override["id"],
        },
    )
    delete_change = delete_preview["changes"][0]
    assert [item["value"] for item in delete_change["before"]] == ["monthly"]
    assert [item["value"] for item in delete_change["after"]] == ["weekly"]
    assert [
        item["value"]
        for item in client.get(f"/employees/{alice['id']}/assignments").json()
    ] == ["monthly"]

    no_op_preview = _preview(
        client,
        {
            "type": "employee_override_change",
            "action": "update",
            "employee_id": alice["id"],
            "override_id": override["id"],
            "value": "monthly",
        },
    )
    assert no_op_preview["affected_employee_count"] == 0
    assert no_op_preview["changes"][0]["added"] == []
    assert no_op_preview["changes"][0]["removed"] == []
    assert no_op_preview["changes"][0]["changed"] == []


def test_policy_version_preview_reconciles_population_without_persisting(client):
    field = _assignment_field(client)
    yesterday = current_date() - timedelta(days=1)
    policy = _policy(
        client,
        field["id"],
        effective_from=yesterday,
    )
    alice = _employee(client)
    bob = _employee(client, name="Bob", state="Texas")

    preview = _preview(
        client,
        {
            "type": "policy_version_create",
            "policy_id": policy["id"],
            "version": {
                "priority": 20,
                "effective_from": current_date().isoformat(),
                "condition_group": _condition("state", "Texas"),
                "values": [
                    {
                        "assignment_field_definition_id": field["id"],
                        "value": "biweekly",
                    }
                ],
            },
        },
    )
    assert preview["valid"] is True
    changes = {
        item["employee_id"]: item
        for item in preview["changes"]
    }
    assert [item["value"] for item in changes[alice["id"]]["removed"]] == [
        "weekly"
    ]
    bob_added = changes[bob["id"]]["added"]
    assert [item["value"] for item in bob_added] == ["biweekly"]
    assert bob_added[0]["source_id"] is None
    assert bob_added[0]["source_is_proposed"] is True

    versions = client.get(f"/policies/{policy['id']}/versions").json()
    assert len(versions) == 1
    assert versions[0]["effective_until"] is None
    assert client.get(f"/employees/{bob['id']}/assignments").json() == []


def test_group_membership_and_override_previews_do_not_persist(client):
    access_field = _assignment_field(client, "application_access", "many")
    policy = _policy(
        client,
        access_field["id"],
        condition_value="Wisconsin",
        value="GitHub",
    )
    alice = _employee(client)
    group = client.post("/groups", json={"name": "Engineering"}).json()
    assert client.post(
        f"/groups/{group['id']}/policies/{policy['id']}"
    ).status_code == 201

    membership_preview = _preview(
        client,
        {
            "type": "group_membership_change",
            "action": "add",
            "group_id": group["id"],
            "employee_id": alice["id"],
        },
    )
    assert [
        item["value"] for item in membership_preview["changes"][0]["added"]
    ] == ["GitHub"]
    assert client.get(f"/groups/{group['id']}/employees").json() == []
    assert client.get(f"/employees/{alice['id']}/assignments").json() == []

    pay_field = _assignment_field(client)
    _policy(client, pay_field["id"], value="weekly")
    override_preview = _preview(
        client,
        {
            "type": "employee_override_change",
            "action": "create",
            "employee_id": alice["id"],
            "assignment_field_definition_id": pay_field["id"],
            "value": "monthly",
        },
    )
    pay_change = next(
        item
        for item in override_preview["changes"][0]["changed"]
        if item["assignment_field_name"] == "pay_schedule"
    )
    assert [item["value"] for item in pay_change["before"]] == ["weekly"]
    assert [item["value"] for item in pay_change["after"]] == ["monthly"]
    assert pay_change["after"][0]["source_is_proposed"] is True
    assert client.get(f"/employees/{alice['id']}/overrides").json() == []
    assert [
        item["value"]
        for item in client.get(f"/employees/{alice['id']}/assignments").json()
    ] == ["weekly"]


def test_preview_returns_policy_conflicts_without_persisting(client):
    field = _assignment_field(client)
    _policy(client, field["id"], value="weekly", priority=10)
    _policy(client, field["id"], value="monthly", priority=10)
    conflict = _preview(
        client,
        {
            "type": "employee_create",
            "employee": {
                "name": "Alice",
                "state": "California",
                "department": "Engineering",
                "employee_type": "regular",
            },
        },
    )
    assert conflict["valid"] is False
    assert conflict["affected_employee_count"] == 0
    assert conflict["conflicts"][0]["code"] == "policy_conflict"
    assert "Conflicting values for field 'pay_schedule'" in conflict["conflicts"][0][
        "message"
    ]
    assert client.get("/employees").json() == []
