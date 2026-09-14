def create_field(client, name="badge", cardinality="one"):
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": cardinality},
    )
    assert response.status_code == 201
    return response.json()


def create_policy(client, name, priority, field_id, value, state="WI"):
    response = client.post(
        "/policies",
        json={
            "name": name,
            "priority": priority,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [{"field": "state", "operator": "=", "value": state}],
            },
            "values": [{"assignment_field_definition_id": field_id, "value": value}],
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


def create_group(client, name="Engineering"):
    response = client.post("/groups", json={"name": name})
    assert response.status_code == 201
    return response.json()


def assignments(client, employee_id):
    response = client.get(f"/employees/{employee_id}/assignments")
    assert response.status_code == 200
    return response.json()


def test_group_crud_and_missing_group_validation(client):
    engineering = create_group(client)
    sales = create_group(client, "Sales")

    assert client.get(f"/groups/{engineering['id']}").json() == engineering
    assert client.get("/groups").json() == [
        {**engineering, "member_count": 0, "policy_count": 0},
        {**sales, "member_count": 0, "policy_count": 0},
    ]

    response = client.patch(f"/groups/{sales['id']}", json={"name": "Revenue"})
    assert response.status_code == 200
    assert response.json() == {"id": sales["id"], "name": "Revenue"}
    assert client.get("/groups/999999").status_code == 404


def test_membership_and_group_policy_changes_reconcile_employee(client):
    field = create_field(client)
    policy = create_policy(client, "Engineering badge", 10, field["id"], "engineer")
    alice = create_employee(client)
    engineering = create_group(client)

    # The policy's Wisconsin condition does not match Alice directly.
    assert assignments(client, alice["id"]) == []
    membership = client.post(f"/groups/{engineering['id']}/employees/{alice['id']}")
    assert membership.status_code == 201
    assert client.get(f"/groups/{engineering['id']}/employees").json() == [alice]

    attached = client.post(f"/groups/{engineering['id']}/policies/{policy['id']}")
    assert attached.status_code == 201
    assert client.get(f"/groups/{engineering['id']}/policies").json() == [policy]
    assert [item["value"] for item in assignments(client, alice["id"])] == ["engineer"]

    # Repeating either operation is idempotent.
    assert client.post(f"/groups/{engineering['id']}/employees/{alice['id']}").status_code == 201
    assert client.post(f"/groups/{engineering['id']}/policies/{policy['id']}").status_code == 201
    assert len(client.get(f"/groups/{engineering['id']}/employees").json()) == 1
    assert len(client.get(f"/groups/{engineering['id']}/policies").json()) == 1

    removed_policy = client.delete(f"/groups/{engineering['id']}/policies/{policy['id']}")
    assert removed_policy.status_code == 204
    assert assignments(client, alice["id"]) == []

    client.post(f"/groups/{engineering['id']}/policies/{policy['id']}")
    assert [item["value"] for item in assignments(client, alice["id"])] == ["engineer"]
    removed_member = client.delete(f"/groups/{engineering['id']}/employees/{alice['id']}")
    assert removed_member.status_code == 204
    assert assignments(client, alice["id"]) == []


def test_batch_membership_update_is_atomic_and_reconciles_all_employees(client):
    field = create_field(client)
    policy = create_policy(client, "Engineering badge", 10, field["id"], "engineer")
    alice = create_employee(client)
    bob = create_employee(client, "Bob")
    carol = create_employee(client, "Carol")
    engineering = create_group(client)
    client.post(f"/groups/{engineering['id']}/policies/{policy['id']}")

    added = client.patch(
        f"/groups/{engineering['id']}/employees",
        json={"add_employee_ids": [alice["id"], bob["id"]], "remove_employee_ids": []},
    )

    assert added.status_code == 204
    assert client.get(f"/groups/{engineering['id']}/employees").json() == [alice, bob]
    assert [item["value"] for item in assignments(client, alice["id"])] == ["engineer"]
    assert [item["value"] for item in assignments(client, bob["id"])] == ["engineer"]

    changed = client.patch(
        f"/groups/{engineering['id']}/employees",
        json={"add_employee_ids": [carol["id"]], "remove_employee_ids": [alice["id"]]},
    )

    assert changed.status_code == 204
    assert client.get(f"/groups/{engineering['id']}/employees").json() == [bob, carol]
    assert assignments(client, alice["id"]) == []
    assert [item["value"] for item in assignments(client, carol["id"])] == ["engineer"]

    invalid = client.patch(
        f"/groups/{engineering['id']}/employees",
        json={"add_employee_ids": [alice["id"], 999999], "remove_employee_ids": [bob["id"]]},
    )

    assert invalid.status_code == 404
    assert client.get(f"/groups/{engineering['id']}/employees").json() == [bob, carol]


def test_batch_policy_update_is_atomic_and_reconciles_members(client):
    field = create_field(client, "application_access", "many")
    github = create_policy(client, "GitHub", 10, field["id"], "GitHub")
    linear = create_policy(client, "Linear", 20, field["id"], "Linear")
    slack = create_policy(client, "Slack", 30, field["id"], "Slack")
    alice = create_employee(client)
    engineering = create_group(client)
    client.post(f"/groups/{engineering['id']}/employees/{alice['id']}")
    client.post(f"/groups/{engineering['id']}/policies/{github['id']}")

    changed = client.patch(
        f"/groups/{engineering['id']}/policies",
        json={
            "add_policy_ids": [linear["id"], slack["id"]],
            "remove_policy_ids": [github["id"]],
        },
    )

    assert changed.status_code == 204
    assert client.get(f"/groups/{engineering['id']}/policies").json() == [linear, slack]
    assert [item["value"] for item in assignments(client, alice["id"])] == [
        "Linear",
        "Slack",
    ]

    invalid = client.patch(
        f"/groups/{engineering['id']}/policies",
        json={
            "add_policy_ids": [github["id"], 999999],
            "remove_policy_ids": [linear["id"]],
        },
    )

    assert invalid.status_code == 404
    assert client.get(f"/groups/{engineering['id']}/policies").json() == [linear, slack]


def test_direct_and_group_policies_use_the_same_priority_engine(client):
    field = create_field(client, "pay_schedule")
    direct = create_policy(
        client,
        "California special schedule",
        100,
        field["id"],
        "monthly",
        state="CA",
    )
    inherited = create_policy(
        client,
        "Engineering schedule",
        10,
        field["id"],
        "weekly",
    )
    alice = create_employee(client)
    engineering = create_group(client)

    initial = assignments(client, alice["id"])
    assert [(item["value"], item["source_policy_version_id"]) for item in initial] == [
        ("monthly", direct["versions"][0]["id"])
    ]

    client.post(f"/groups/{engineering['id']}/employees/{alice['id']}")
    client.post(f"/groups/{engineering['id']}/policies/{inherited['id']}")

    resolved = assignments(client, alice["id"])
    assert [(item["value"], item["source_policy_version_id"]) for item in resolved] == [
        ("monthly", direct["versions"][0]["id"])
    ]


def test_policy_inherited_through_multiple_groups_is_deduplicated(client):
    field = create_field(client, "application_access", "many")
    policy = create_policy(client, "GitHub Access", 10, field["id"], "GitHub")
    alice = create_employee(client)
    bob = create_employee(client, "Bob")
    engineering = create_group(client)
    platform = create_group(client, "Platform")

    for group_id, employee_id in [
        (engineering["id"], alice["id"]),
        (engineering["id"], bob["id"]),
        (platform["id"], alice["id"]),
    ]:
        assert client.post(f"/groups/{group_id}/employees/{employee_id}").status_code == 201

    client.post(f"/groups/{engineering['id']}/policies/{policy['id']}")
    client.post(f"/groups/{platform['id']}/policies/{policy['id']}")
    assert [item["value"] for item in assignments(client, alice["id"])] == ["GitHub"]
    assert [item["value"] for item in assignments(client, bob["id"])] == ["GitHub"]

    client.delete(f"/groups/{engineering['id']}/policies/{policy['id']}")
    assert [item["value"] for item in assignments(client, alice["id"])] == ["GitHub"]
    assert assignments(client, bob["id"]) == []

    client.delete(f"/groups/{platform['id']}/policies/{policy['id']}")
    assert assignments(client, alice["id"]) == []


def test_conflicting_group_policy_attachment_rolls_back(client):
    field = create_field(client, "pay_schedule")
    weekly = create_policy(client, "Weekly", 10, field["id"], "weekly")
    monthly = create_policy(client, "Monthly", 10, field["id"], "monthly")
    alice = create_employee(client)
    engineering = create_group(client)
    client.post(f"/groups/{engineering['id']}/employees/{alice['id']}")
    client.post(f"/groups/{engineering['id']}/policies/{weekly['id']}")

    response = client.post(f"/groups/{engineering['id']}/policies/{monthly['id']}")

    assert response.status_code == 409
    assert client.get(f"/groups/{engineering['id']}/policies").json() == [weekly]
    assert [item["value"] for item in assignments(client, alice["id"])] == ["weekly"]


def test_membership_and_policy_endpoints_validate_references(client):
    employee = create_employee(client)
    group = create_group(client)
    field = create_field(client)
    policy = create_policy(client, "Badge", 1, field["id"], "blue")

    assert client.post(f"/groups/999999/employees/{employee['id']}").status_code == 404
    assert client.post(f"/groups/{group['id']}/employees/999999").status_code == 404
    assert client.post(f"/groups/999999/policies/{policy['id']}").status_code == 404
    assert client.post(f"/groups/{group['id']}/policies/999999").status_code == 404
