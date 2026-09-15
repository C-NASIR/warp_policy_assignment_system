from datetime import timedelta

from app.dates import current_date


def _field(client, name: str = "pay_schedule") -> dict:
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": "one"},
    )
    assert response.status_code == 201
    return response.json()


def _policy(
    client,
    field_id: int,
    *,
    name: str,
    priority: int,
    condition_field: str,
    condition_value: str,
    value: str,
) -> dict:
    response = client.post(
        "/policies",
        json={
            "name": name,
            "priority": priority,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {
                        "field": condition_field,
                        "operator": "=",
                        "value": condition_value,
                    }
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": field_id,
                    "value": value,
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def _employee(client, *, state: str = "CA") -> dict:
    response = client.post(
        "/employees",
        json={
            "name": "Alice",
            "state": state,
            "department": "Engineering",
            "employee_type": "regular",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_assignment_explains_condition_match_and_priority_competition(client):
    field = _field(client)
    california = _policy(
        client,
        field["id"],
        name="California Policy",
        priority=20,
        condition_field="state",
        condition_value="CA",
        value="biweekly",
    )
    engineering = _policy(
        client,
        field["id"],
        name="Engineering Policy",
        priority=10,
        condition_field="department",
        condition_value="Engineering",
        value="weekly",
    )
    employee = _employee(client)

    assignment = client.get(
        f"/employees/{employee['id']}/assignments"
    ).json()[0]
    explanation = assignment["explanation"]
    assert explanation["reason"] == "policy"
    assert explanation["policy"] == {"name": "California Policy"}
    condition = explanation["origins"][0]["matched_clauses"][0][
        "conditions"
    ][0]
    assert condition == {
        "field": "state",
        "operator": "=",
        "expected": "CA",
        "actual": "CA",
        "expected_label": "California",
        "actual_label": "California",
    }
    assert explanation["selection"] == {
        "priority": 20,
        "replaced_policy_assignments": [],
    }
    assert "candidates" not in explanation["selection"]


def test_group_origin_and_changed_reason_create_assignment_history(client):
    field = _field(client)
    policy = _policy(
        client,
        field["id"],
        name="California Policy",
        priority=20,
        condition_field="state",
        condition_value="CA",
        value="biweekly",
    )
    employee = _employee(client)
    group = client.post("/groups", json={"name": "California Employees"}).json()
    assert client.post(
        f"/groups/{group['id']}/employees/{employee['id']}"
    ).status_code == 201
    assert client.post(
        f"/groups/{group['id']}/policies/{policy['id']}"
    ).status_code == 201

    history = client.get(
        f"/employees/{employee['id']}/assignments/history"
    ).json()
    assert len(history) == 2
    assert "explanation" not in history[0]
    historical = client.get(
        f"/employees/{employee['id']}/assignments",
        params={"as_of": history[0]["effective_from"]},
    ).json()
    assert [
        origin["type"] for origin in historical[0]["explanation"]["origins"]
    ] == ["condition_match"]
    current = client.get(f"/employees/{employee['id']}/assignments").json()
    assert [
        origin["type"] for origin in current[0]["explanation"]["origins"]
    ] == ["condition_match", "group"]
    group_origin = current[0]["explanation"]["origins"][1]
    assert group_origin == {
        "type": "group",
        "group_name": "California Employees",
        "matched_clauses": [],
    }
    assert history[0]["effective_until"] is not None

    assert client.patch(
        f"/employees/{employee['id']}",
        json={"state": "WI"},
    ).status_code == 200
    history = client.get(
        f"/employees/{employee['id']}/assignments/history"
    ).json()
    assert len(history) == 3
    current = client.get(f"/employees/{employee['id']}/assignments").json()
    assert [
        origin["type"] for origin in current[0]["explanation"]["origins"]
    ] == ["group"]


def test_override_and_future_projection_include_explanations(client):
    field = _field(client)
    policy = _policy(
        client,
        field["id"],
        name="California Policy",
        priority=20,
        condition_field="state",
        condition_value="CA",
        value="biweekly",
    )
    employee = _employee(client)
    override = client.post(
        f"/employees/{employee['id']}/overrides",
        json={
            "assignment_field_definition_id": field["id"],
            "value": "monthly",
        },
    )
    assert override.status_code == 201

    current = client.get(f"/employees/{employee['id']}/assignments").json()[0]
    explanation = current["explanation"]
    assert explanation["reason"] == "manual_override"
    assert explanation["override"] == {"value": "monthly"}
    assert explanation["selection"]["replaced_policy_assignments"] == [
        {
            "value": "biweekly",
            "policy_name": "California Policy",
        }
    ]

    future = client.post(
        "/assignment-queries",
        json={
            "employee_ids": [employee["id"]],
            "evaluation_date": (
                current_date() + timedelta(days=30)
            ).isoformat(),
        },
    )
    assert future.status_code == 200
    projected = future.json()[0]["assignments"][0]
    assert projected["value"] == "monthly"
    assert projected["explanation"]["reason"] == "manual_override"
    assert projected["explanation"]["override"] == {
        "id": override.json()["id"],
        "value": "monthly",
    }
    assert projected["explanation"]["selection"]["replaced_policy_assignments"] == [
        {
            "value": "biweekly",
            "source_policy_version_id": policy["versions"][0]["id"],
            "policy_name": "California Policy",
        }
    ]
    assert projected["explanation"]["evaluation_date"] == (
        current_date() + timedelta(days=30)
    ).isoformat()
