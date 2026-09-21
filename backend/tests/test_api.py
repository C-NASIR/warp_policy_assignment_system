from app.dates import current_date


def create_field(client, name, cardinality):
    response = client.post(
        "/assignment-fields", json={"name": name, "cardinality": cardinality}
    )
    assert response.status_code == 201
    return response.json()


def condition_group(field, value):
    return {
        "logical_operator": "and",
        "conditions": [{"field": field, "operator": "=", "value": value}],
    }


def create_policy(client, name, priority, condition_tree, values):
    response = client.post(
        "/policies",
        json={
            "name": name,
            "priority": priority,
            "condition_group": condition_tree,
            "values": values,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_alice_scenario_reconciles_policies_and_assignments(client):
    pay = create_field(client, "pay_schedule", "one")
    access = create_field(client, "application_access", "many")
    california_policy = create_policy(
        client,
        "California Policy",
        20,
        condition_group("state", "CA"),
        [
            {"assignment_field_definition_id": pay["id"], "value": "biweekly"},
            {"assignment_field_definition_id": access["id"], "value": "payroll_app"},
        ],
    )
    engineering_policy = create_policy(
        client,
        "Engineering Policy",
        10,
        condition_group("department", "Engineering"),
        [
            {"assignment_field_definition_id": pay["id"], "value": "weekly"},
            {"assignment_field_definition_id": access["id"], "value": "GitHub"},
        ],
    )

    response = client.post(
        "/employees",
        json={
            "name": "Alice",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
        },
    )
    assert response.status_code == 201
    alice = response.json()

    assignments = client.get(f"/employees/{alice['id']}/assignments").json()
    by_value = {assignment["value"]: assignment for assignment in assignments}
    assert set(by_value) == {"biweekly", "payroll_app", "GitHub"}
    california_version_id = california_policy["versions"][0]["id"]
    engineering_version_id = engineering_policy["versions"][0]["id"]
    assert by_value["biweekly"]["source_policy_version_id"] == california_version_id
    assert by_value["payroll_app"]["source_policy_version_id"] == california_version_id
    assert by_value["GitHub"]["source_policy_version_id"] == engineering_version_id
    assert by_value["biweekly"]["assignment_field_definition"]["name"] == "pay_schedule"
    directory_entry = next(
        item for item in client.get("/employees").json() if item["id"] == alice["id"]
    )
    assert directory_entry["active_assignment_count"] == 3

    response = client.patch(f"/employees/{alice['id']}", json={"state": "WI"})
    assert response.status_code == 200
    assignments = client.get(f"/employees/{alice['id']}/assignments").json()
    assert {assignment["value"] for assignment in assignments} == {"weekly", "GitHub"}
    assert {assignment["source_policy_version_id"] for assignment in assignments} == {
        engineering_version_id
    }
    directory_entry = next(
        item for item in client.get("/employees").json() if item["id"] == alice["id"]
    )
    assert directory_entry["active_assignment_count"] == 2


def test_nonmatching_policy_produces_no_assignment_then_employee_update_applies_it(
    client,
):
    field = create_field(client, "badge", "one")
    employee = client.post(
        "/employees",
        json={
            "name": "Bob",
            "state": "TX",
            "department": "Sales",
            "employee_type": "contractor",
        },
    ).json()
    create_policy(
        client,
        "Regular badge",
        1,
        condition_group("employee_type", "regular"),
        [{"assignment_field_definition_id": field["id"], "value": "blue"}],
    )
    assert client.post(f"/employees/{employee['id']}/refresh").json() == []

    client.patch(f"/employees/{employee['id']}", json={"employee_type": "regular"})
    assignments = client.get(f"/employees/{employee['id']}/assignments").json()
    assert [assignment["value"] for assignment in assignments] == ["blue"]


def test_equal_priority_conflict_is_clear_and_employee_creation_rolls_back(client):
    field = create_field(client, "pay_schedule", "one")
    create_policy(
        client,
        "State policy",
        10,
        condition_group("state", "CA"),
        [{"assignment_field_definition_id": field["id"], "value": "weekly"}],
    )
    create_policy(
        client,
        "Department policy",
        10,
        condition_group("department", "Engineering"),
        [{"assignment_field_definition_id": field["id"], "value": "monthly"}],
    )

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
    assert (
        "Conflicting values for field 'pay_schedule'"
        in response.json()["error"]["message"]
    )
    assert client.get("/employees").json() == []


def test_validation_and_missing_references(client):
    assert (
        client.post(
            "/assignment-fields", json={"name": "x", "cardinality": "some"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/policies", json={"name": "missing tree", "priority": 1}
        ).status_code
        == 422
    )

    response = client.post(
        "/policies",
        json={
            "name": "bad value",
            "priority": 1,
            "condition_group": condition_group("department", "Engineering"),
            "values": [{"assignment_field_definition_id": 999, "value": "x"}],
        },
    )
    assert response.status_code == 404
    assert client.get("/employees/999").status_code == 404


def test_archiving_policy_removes_it_on_employee_reconciliation(client):
    badge = create_field(client, "badge", "one")
    policy = create_policy(
        client,
        "State badge",
        10,
        condition_group("state", "CA"),
        [{"assignment_field_definition_id": badge["id"], "value": "blue"}],
    )
    alice = client.post(
        "/employees",
        json={
            "name": "Alice",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
        },
    ).json()
    assert [
        item["value"]
        for item in client.get(f"/employees/{alice['id']}/assignments").json()
    ] == ["blue"]

    response = client.patch(
        f"/policies/{policy['id']}",
        json={"status": "archived"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "archived"
    assert client.post(f"/employees/{alice['id']}/refresh").json() == []


def test_policy_update_validates_nested_tree_and_value_references(client):
    field = create_field(client, "badge", "one")
    policy = create_policy(
        client,
        "State badge",
        10,
        condition_group("state", "CA"),
        [{"assignment_field_definition_id": field["id"], "value": "blue"}],
    )

    empty_tree = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 10,
            "condition_group": {"logical_operator": "and"},
        },
    )
    assert empty_tree.status_code == 422

    missing_field = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 10,
            "condition_group": condition_group("state", "CA"),
            "values": [{"assignment_field_definition_id": 999, "value": "red"}],
        },
    )
    assert missing_field.status_code == 404

    executable_patch = client.patch(
        f"/policies/{policy['id']}",
        json={"priority": 99},
    )
    assert executable_patch.status_code == 422


def test_policy_accepts_round_trips_and_evaluates_three_group_levels(client):
    root = {
        "name": "Root Admin",
        "email": "root@example.com",
        "password": "root password for nested policy testing",
    }
    assert client.post("/auth/setup-root", json=root).status_code == 201
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"
    assert (
        client.post(
            "/auth/login",
            json={"email": root["email"], "password": root["password"]},
        ).status_code
        == 200
    )

    field = create_field(client, "regional_badge", "one")
    condition_tree = {
        "logical_operator": "and",
        "conditions": [
            {"field": "employee_type", "operator": "=", "value": "regular"}
        ],
        "child_groups": [
            {
                "logical_operator": "or",
                "conditions": [
                    {"field": "state", "operator": "=", "value": "CA"},
                    {"field": "state", "operator": "=", "value": "NY"},
                ],
            },
            {
                "logical_operator": "and",
                "conditions": [
                    {
                        "field": "department",
                        "operator": "=",
                        "value": "Engineering",
                    }
                ],
                "child_groups": [
                    {
                        "logical_operator": "or",
                        "conditions": [
                            {
                                "field": "location",
                                "operator": "=",
                                "value": "Chicago",
                            },
                            {
                                "field": "location",
                                "operator": "=",
                                "value": "Remote",
                            },
                        ],
                    }
                ],
            },
        ],
    }
    policy = create_policy(
        client,
        "Regional engineering badge",
        10,
        condition_tree,
        [{"assignment_field_definition_id": field["id"], "value": "eligible"}],
    )

    persisted_tree = policy["versions"][0]["condition_group"]
    assert len(persisted_tree["child_groups"]) == 2
    assert len(persisted_tree["child_groups"][1]["child_groups"]) == 1

    employee = client.post(
        "/employees",
        json={
            "name": "Nested Match",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
            "location": "Chicago",
        },
    ).json()
    assignments = client.get(f"/employees/{employee['id']}/assignments").json()
    assert [assignment["value"] for assignment in assignments] == ["eligible"]


def test_employee_date_comparison_policy_is_accepted_and_applied(client):
    badge = create_field(client, "tenure_badge", "one")
    response = client.post(
        "/policies",
        json={
            "name": "Started by 2024",
            "priority": 1,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "start_date", "operator": "<=", "value": "2024-12-31"}
                ],
            },
            "values": [
                {"assignment_field_definition_id": badge["id"], "value": "tenured"}
            ],
        },
    )
    assert response.status_code == 201

    employee = client.post(
        "/employees",
        json={
            "name": "Alice",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
            "location": "San Francisco",
            "start_date": "2024-02-01",
        },
    )
    assert employee.status_code == 201
    assert employee.json()["start_date"] == "2024-02-01"
    assignments = client.get(f"/employees/{employee.json()['id']}/assignments").json()
    assert [item["value"] for item in assignments] == ["tenured"]


def test_policy_rejects_an_unknown_comparison_operator(client):
    response = client.post(
        "/policies",
        json={
            "name": "Unsupported",
            "priority": 1,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {
                        "field": "start_date",
                        "operator": "contains",
                        "value": "2024-12-31",
                    }
                ],
            },
        },
    )

    assert response.status_code == 422


def test_policy_rejects_invalid_typed_condition_values(client):
    response = client.post(
        "/policies",
        json={
            "name": "Invalid typed value",
            "priority": 1,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "start_date", "operator": "<", "value": "last Tuesday"}
                ],
            },
        },
    )

    assert response.status_code == 422


def test_employee_start_date_defaults_to_current_date(client):
    response = client.post(
        "/employees",
        json={
            "name": "New starter",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
        },
    )

    assert response.status_code == 201
    assert response.json()["start_date"] == current_date().isoformat()


def test_employee_manager_id_can_be_created_and_updated(client):
    first_manager = client.post(
        "/employees",
        json={
            "name": "First manager",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
        },
    ).json()
    second_manager = client.post(
        "/employees",
        json={
            "name": "Second manager",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
        },
    ).json()
    response = client.post(
        "/employees",
        json={
            "name": "New starter",
            "state": "CA",
            "department": "Engineering",
            "employee_type": "regular",
            "manager_id": first_manager["id"],
        },
    )
    assert response.status_code == 201
    assert response.json()["manager_id"] == first_manager["id"]

    updated = client.patch(
        f"/employees/{response.json()['id']}",
        json={"manager_id": second_manager["id"]},
    )
    assert updated.status_code == 200
    assert updated.json()["manager_id"] == second_manager["id"]
    detail = client.get(f"/employees/{response.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["manager"] == {
        "id": second_manager["id"],
        "name": "Second manager",
    }
