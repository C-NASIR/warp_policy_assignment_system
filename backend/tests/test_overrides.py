def create_field(client, name, cardinality="one"):
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": cardinality},
    )
    assert response.status_code == 201
    return response.json()


def create_policy(client, name, priority, values, state="CA"):
    response = client.post(
        "/policies",
        json={
            "name": name,
            "priority": priority,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [{"field": "state", "operator": "=", "value": state}],
            },
            "values": values,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_employee(client, name="Alice"):
    response = client.post(
        "/employees",
        json={
            "name": name,
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
        },
    )
    assert response.status_code == 201
    return response.json()


def assignments(client, employee_id):
    response = client.get(f"/employees/{employee_id}/assignments")
    assert response.status_code == 200
    return response.json()


def test_one_value_override_replaces_updates_and_restores_policy_result(client):
    schedule = create_field(client, "pay_schedule")
    policy = create_policy(
        client,
        "Weekly schedule",
        10,
        [{"assignment_field_definition_id": schedule["id"], "value": "weekly"}],
    )
    employee = create_employee(client)
    initial = assignments(client, employee["id"])
    assert initial[0]["value"] == "weekly"
    assert initial[0]["source_policy_version_id"] == policy["versions"][0]["id"]
    assert initial[0]["source_override_id"] is None

    response = client.post(
        f"/employees/{employee['id']}/overrides",
        json={"assignment_field_definition_id": schedule["id"], "value": "monthly"},
    )
    assert response.status_code == 201
    override = response.json()
    assert client.get(f"/employees/{employee['id']}/overrides").json() == [override]

    overridden = assignments(client, employee["id"])
    assert overridden[0]["value"] == "monthly"
    assert overridden[0]["source_policy_version_id"] is None
    assert overridden[0]["source_override_id"] == override["id"]

    updated = client.patch(
        f"/employees/{employee['id']}/overrides/{override['id']}",
        json={"value": "biweekly"},
    )
    assert updated.status_code == 200
    replacement = updated.json()
    assert replacement["value"] == "biweekly"
    assert replacement["id"] != override["id"]
    assert assignments(client, employee["id"])[0]["value"] == "biweekly"

    deleted = client.delete(
        f"/employees/{employee['id']}/overrides/{replacement['id']}"
    )
    assert deleted.status_code == 204
    restored = assignments(client, employee["id"])
    assert restored[0]["value"] == "weekly"
    assert restored[0]["source_policy_version_id"] == policy["versions"][0]["id"]
    assert restored[0]["source_override_id"] is None

    history = client.get(
        f"/employees/{employee['id']}/assignments/history"
    ).json()
    assert [item["value"] for item in history] == [
        "weekly",
        "monthly",
        "biweekly",
        "weekly",
    ]
    assert [item["source_override_id"] for item in history] == [
        None,
        override["id"],
        replacement["id"],
        None,
    ]
    assert all(item["effective_until"] is not None for item in history[:-1])
    assert history[-1]["effective_until"] is None

    at_override_start = client.get(
        f"/employees/{employee['id']}/assignments",
        params={"as_of": history[1]["effective_from"]},
    )
    assert at_override_start.status_code == 200
    assert [item["value"] for item in at_override_start.json()] == ["monthly"]


def test_override_can_create_an_assignment_without_a_policy_value(client):
    badge = create_field(client, "badge")
    employee = create_employee(client)

    response = client.post(
        f"/employees/{employee['id']}/overrides",
        json={"assignment_field_definition_id": badge["id"], "value": "gold"},
    )

    assert response.status_code == 201
    result = assignments(client, employee["id"])
    assert [(item["value"], item["source_override_id"]) for item in result] == [
        ("gold", response.json()["id"])
    ]


def test_many_value_overrides_replace_all_policy_values_until_last_is_removed(client):
    access = create_field(client, "application_access", "many")
    create_policy(
        client,
        "Default applications",
        10,
        [
            {"assignment_field_definition_id": access["id"], "value": "GitHub"},
            {"assignment_field_definition_id": access["id"], "value": "Slack"},
        ],
    )
    employee = create_employee(client)
    assert {item["value"] for item in assignments(client, employee["id"])} == {
        "GitHub",
        "Slack",
    }

    linear = client.post(
        f"/employees/{employee['id']}/overrides",
        json={"assignment_field_definition_id": access["id"], "value": "Linear"},
    ).json()
    figma_response = client.post(
        f"/employees/{employee['id']}/overrides",
        json={"assignment_field_definition_id": access["id"], "value": "Figma"},
    )
    assert figma_response.status_code == 201
    figma = figma_response.json()
    overridden = assignments(client, employee["id"])
    assert {item["value"] for item in overridden} == {"Linear", "Figma"}
    assert all(item["source_policy_version_id"] is None for item in overridden)

    duplicate = client.post(
        f"/employees/{employee['id']}/overrides",
        json={"assignment_field_definition_id": access["id"], "value": "Figma"},
    )
    assert duplicate.status_code == 409

    client.delete(f"/employees/{employee['id']}/overrides/{linear['id']}")
    assert [item["value"] for item in assignments(client, employee["id"])] == ["Figma"]
    client.delete(f"/employees/{employee['id']}/overrides/{figma['id']}")
    assert {item["value"] for item in assignments(client, employee["id"])} == {
        "GitHub",
        "Slack",
    }


def test_one_value_field_rejects_a_second_override(client):
    schedule = create_field(client, "pay_schedule")
    employee = create_employee(client)
    first = client.post(
        f"/employees/{employee['id']}/overrides",
        json={"assignment_field_definition_id": schedule["id"], "value": "weekly"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/employees/{employee['id']}/overrides",
        json={"assignment_field_definition_id": schedule["id"], "value": "monthly"},
    )

    assert second.status_code == 409
    assert [item["value"] for item in assignments(client, employee["id"])] == ["weekly"]


def test_override_endpoints_validate_references_ownership_and_updates(client):
    field = create_field(client, "badge")
    alice = create_employee(client)
    bob = create_employee(client, "Bob")
    override = client.post(
        f"/employees/{alice['id']}/overrides",
        json={"assignment_field_definition_id": field["id"], "value": "gold"},
    ).json()

    assert client.post(
        "/employees/999999/overrides",
        json={"assignment_field_definition_id": field["id"], "value": "x"},
    ).status_code == 404
    assert client.post(
        f"/employees/{alice['id']}/overrides",
        json={"assignment_field_definition_id": 999999, "value": "x"},
    ).status_code == 404
    assert client.patch(
        f"/employees/{bob['id']}/overrides/{override['id']}",
        json={"value": "silver"},
    ).status_code == 404
    assert client.delete(
        f"/employees/{bob['id']}/overrides/{override['id']}"
    ).status_code == 404
    assert client.patch(
        f"/employees/{alice['id']}/overrides/{override['id']}",
        json={},
    ).status_code == 422


def test_override_does_not_hide_an_equal_priority_policy_conflict(client):
    schedule = create_field(client, "pay_schedule")
    weekly = create_policy(
        client,
        "Weekly",
        10,
        [{"assignment_field_definition_id": schedule["id"], "value": "weekly"}],
        state="WI",
    )
    monthly = create_policy(
        client,
        "Monthly",
        10,
        [{"assignment_field_definition_id": schedule["id"], "value": "monthly"}],
        state="WI",
    )
    employee = create_employee(client)
    group = client.post("/groups", json={"name": "Engineering"}).json()
    client.post(f"/groups/{group['id']}/employees/{employee['id']}")
    client.post(f"/groups/{group['id']}/policies/{weekly['id']}")
    override = client.post(
        f"/employees/{employee['id']}/overrides",
        json={"assignment_field_definition_id": schedule["id"], "value": "quarterly"},
    )
    assert override.status_code == 201

    conflict = client.post(f"/groups/{group['id']}/policies/{monthly['id']}")

    assert conflict.status_code == 409
    assert client.get(f"/groups/{group['id']}/policies").json() == [weekly]
    result = assignments(client, employee["id"])
    assert [item["value"] for item in result] == ["quarterly"]
    assert result[0]["source_override_id"] == override.json()["id"]
