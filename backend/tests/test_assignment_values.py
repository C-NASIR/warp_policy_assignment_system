def _condition_group():
    return {
        "logical_operator": "and",
        "conditions": [{"field": "state", "operator": "=", "value": "CA"}],
    }


def _select_field(client):
    response = client.post(
        "/assignment-fields",
        json={
            "name": "Pay Schedule",
            "cardinality": "one",
            "input": {
                "type": "select",
                "options": [
                    {"value": "Weekly", "label": "Weekly"},
                    {"value": "Biweekly", "label": "Biweekly"},
                ],
            },
        },
    )
    assert response.status_code == 201
    return response.json()


def test_select_assignment_field_accepts_only_declared_values(client):
    field = _select_field(client)
    assert field["input"]["type"] == "select"
    assert [option["value"] for option in field["input"]["options"]] == [
        "Weekly",
        "Biweekly",
    ]

    valid = client.post(
        "/policies",
        json={
            "name": "Valid schedule",
            "priority": 1,
            "condition_group": _condition_group(),
            "values": [
                {
                    "assignment_field_definition_id": field["id"],
                    "value": "Biweekly",
                }
            ],
        },
    )
    assert valid.status_code == 201

    invalid = client.post(
        "/policies",
        json={
            "name": "Misspelled schedule",
            "priority": 1,
            "condition_group": _condition_group(),
            "values": [
                {
                    "assignment_field_definition_id": field["id"],
                    "value": "Bi-weekly",
                }
            ],
        },
    )
    assert invalid.status_code == 422
    assert "not an allowed option" in invalid.json()["error"]["issues"][0]["message"]


def test_select_assignment_field_validates_manual_overrides(client):
    field = _select_field(client)
    employee = client.post(
        "/employees",
        json={
            "name": "Alice",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "Full-time",
        },
    ).json()

    invalid = client.post(
        f"/employees/{employee['id']}/overrides",
        json={
            "assignment_field_definition_id": field["id"],
            "value": "Whenever",
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request_validation_failed"
    assert invalid.json()["error"]["issues"][0]["code"] == "invalid_assignment_value"


def test_assignment_field_input_definition_rejects_missing_or_duplicate_options(client):
    missing = client.post(
        "/assignment-fields",
        json={
            "name": "Missing options",
            "cardinality": "one",
            "input": {"type": "select", "options": []},
        },
    )
    assert missing.status_code == 422

    duplicate = client.post(
        "/assignment-fields",
        json={
            "name": "Duplicate options",
            "cardinality": "one",
            "input": {
                "type": "select",
                "options": [
                    {"value": "Slack", "label": "Slack"},
                    {"value": "slack", "label": "Slack duplicate"},
                ],
            },
        },
    )
    assert duplicate.status_code == 422


def test_assignment_field_options_can_be_updated_without_rewriting_history(client):
    field = _select_field(client)
    policy = client.post(
        "/policies",
        json={
            "name": "Existing schedule",
            "priority": 1,
            "condition_group": _condition_group(),
            "values": [
                {
                    "assignment_field_definition_id": field["id"],
                    "value": "Biweekly",
                }
            ],
        },
    ).json()

    updated = client.patch(
        f"/assignment-fields/{field['id']}",
        json={
            "input": {
                "type": "select",
                "options": [{"value": "Weekly", "label": "Weekly"}],
            }
        },
    )
    assert updated.status_code == 200
    assert updated.json()["input"]["options"] == [
        {"value": "Weekly", "label": "Weekly"}
    ]
    assert (
        client.get(f"/policies/{policy['id']}").json()["versions"][0]["values"][0][
            "value"
        ]
        == "Biweekly"
    )

    rejected = client.post(
        "/policies",
        json={
            "name": "New retired schedule",
            "priority": 1,
            "condition_group": _condition_group(),
            "values": [
                {
                    "assignment_field_definition_id": field["id"],
                    "value": "Biweekly",
                }
            ],
        },
    )
    assert rejected.status_code == 422
