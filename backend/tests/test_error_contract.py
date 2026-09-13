def _field(client, name="pay_schedule"):
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": "one"},
    )
    assert response.status_code == 201
    return response.json()


def _policy(client, field_id, name, value):
    response = client.post(
        "/policies",
        json={
            "name": name,
            "priority": 10,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {
                        "field": "state",
                        "operator": "=",
                        "value": "CA",
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


def test_request_validation_errors_have_stable_codes_and_paths(client):
    response = client.post(
        "/assignment-fields",
        json={"name": "pay_schedule", "cardinality": "invalid"},
    )

    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"] == {
        "category": "validation",
        "code": "request_validation_failed",
        "message": "Request validation failed",
        "issues": [
            {
                "code": "literal_error",
                "message": "Input should be 'one' or 'many'",
                "path": ["body", "cardinality"],
                "metadata": {"expected": "'one' or 'many'"},
            }
        ],
    }


def test_manual_validation_errors_use_the_same_envelope(client):
    response = client.post(
        "/employees",
        headers={"X-Actor": " "},
        json={
            "name": "Alice",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["category"] == "validation"
    assert body["error"]["code"] == "request_validation_failed"
    assert body["error"]["issues"] == [
        {
            "code": "invalid_request",
            "message": "X-Actor cannot be blank",
            "path": [],
            "metadata": {},
        }
    ]


def test_policy_conflicts_include_field_and_candidate_metadata(client):
    field = _field(client)
    weekly = _policy(client, field["id"], "Weekly", "weekly")
    monthly = _policy(client, field["id"], "Monthly", "monthly")

    response = client.post(
        "/employees",
        json={
            "name": "Alice",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["category"] == "conflict"
    assert body["error"]["code"] == "policy_conflict"
    issue = body["error"]["issues"][0]
    assert issue["code"] == "policy_conflict"
    assert issue["path"] == ["assignments", "pay_schedule"]
    assert issue["metadata"]["assignment_field_definition_id"] == field["id"]
    assert issue["metadata"]["assignment_field_name"] == "pay_schedule"
    assert issue["metadata"]["priority"] == 10
    assert {
        (candidate["policy_id"], candidate["value"])
        for candidate in issue["metadata"]["candidates"]
    } == {
        (weekly["id"], "weekly"),
        (monthly["id"], "monthly"),
    }


def test_generic_http_conflicts_are_also_structured(client):
    _field(client, "badge")
    response = client.post(
        "/assignment-fields",
        json={"name": "badge", "cardinality": "one"},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["category"] == "conflict"
    assert body["error"]["code"] == "conflict"
    assert body["error"]["issues"][0]["code"] == "conflict"
