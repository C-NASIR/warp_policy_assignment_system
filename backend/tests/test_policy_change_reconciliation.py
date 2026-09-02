from datetime import timedelta

from sqlalchemy import select

from app.dates import current_date
from app.models import EmployeePolicy


def _create_field(client, name="pay_schedule", cardinality="one"):
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": cardinality},
    )
    assert response.status_code == 201
    return response.json()


def _create_employee(client, name, state):
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


def _condition(field, value):
    return {
        "logical_operator": "and",
        "conditions": [{"field": field, "operator": "=", "value": value}],
    }


def _create_policy(
    client,
    field,
    *,
    name,
    condition_field,
    condition_value,
    value,
    priority=10,
    effective_from=None,
):
    body = {
        "name": name,
        "priority": priority,
        "condition_group": _condition(condition_field, condition_value),
        "values": [{"assignment_field_definition_id": field["id"], "value": value}],
    }
    if effective_from is not None:
        body["effective_from"] = effective_from.isoformat()
    response = client.post("/policies", json=body)
    assert response.status_code == 201
    return response.json()


def _assignments(client, employee):
    response = client.get(f"/employees/{employee['id']}/assignments")
    assert response.status_code == 200
    return response.json()


def _assignment_history(client, employee):
    response = client.get(f"/employees/{employee['id']}/assignments/history")
    assert response.status_code == 200
    return response.json()


def _audit_logs(client):
    response = client.get("/audit-logs")
    assert response.status_code == 200
    return response.json()


def _employee_policy_ids(db, employee):
    db.expire_all()
    return list(
        db.scalars(
            select(EmployeePolicy.policy_id)
            .where(EmployeePolicy.employee_id == employee["id"])
            .order_by(EmployeePolicy.policy_id)
        )
    )


def test_policy_creation_synchronously_reconciles_existing_matching_employees(client):
    field = _create_field(client)
    alice = _create_employee(client, "Alice", "California")
    bob = _create_employee(client, "Bob", "Texas")

    policy = _create_policy(
        client,
        field,
        name="California payroll",
        condition_field="state",
        condition_value="California",
        value="weekly",
    )

    alice_assignments = _assignments(client, alice)
    assert [(item["value"], item["source_policy_version_id"]) for item in alice_assignments] == [
        ("weekly", policy["versions"][0]["id"])
    ]
    assert _assignments(client, bob) == []
    assert _assignment_history(client, bob) == []


def test_new_current_version_reconciles_employees_that_enter_and_leave_policy(client):
    field = _create_field(client)
    yesterday = current_date() - timedelta(days=1)
    policy = _create_policy(
        client,
        field,
        name="Regional payroll",
        condition_field="state",
        condition_value="California",
        value="weekly",
        effective_from=yesterday,
    )
    alice = _create_employee(client, "Alice", "California")
    bob = _create_employee(client, "Bob", "Texas")
    alice_original = _assignments(client, alice)[0]
    assert _assignments(client, bob) == []

    response = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 10,
            "effective_from": current_date().isoformat(),
            "condition_group": _condition("state", "Texas"),
            "values": [{"assignment_field_definition_id": field["id"], "value": "biweekly"}],
        },
    )
    assert response.status_code == 201
    new_version = response.json()

    assert _assignments(client, alice) == []
    alice_history = _assignment_history(client, alice)
    assert len(alice_history) == 1
    assert alice_history[0]["id"] == alice_original["id"]
    assert alice_history[0]["effective_until"] is not None

    bob_assignments = _assignments(client, bob)
    assert [(item["value"], item["source_policy_version_id"]) for item in bob_assignments] == [
        ("biweekly", new_version["id"])
    ]


def test_future_policy_version_does_not_change_current_assignments(client):
    field = _create_field(client)
    policy = _create_policy(
        client,
        field,
        name="Scheduled payroll change",
        condition_field="state",
        condition_value="California",
        value="weekly",
        effective_from=current_date() - timedelta(days=1),
    )
    alice = _create_employee(client, "Alice", "California")
    original = _assignments(client, alice)[0]

    response = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 20,
            "effective_from": (current_date() + timedelta(days=1)).isoformat(),
            "condition_group": _condition("state", "California"),
            "values": [{"assignment_field_definition_id": field["id"], "value": "biweekly"}],
        },
    )
    assert response.status_code == 201

    assert _assignments(client, alice) == [original]
    assert _assignment_history(client, alice) == [original]


def test_archiving_and_reactivating_policy_reconcile_direct_assignments(client):
    field = _create_field(client, "badge")
    policy = _create_policy(
        client,
        field,
        name="California badge",
        condition_field="state",
        condition_value="California",
        value="blue",
    )
    alice = _create_employee(client, "Alice", "California")
    first = _assignments(client, alice)[0]

    archived = client.patch(f"/policies/{policy['id']}", json={"status": "archived"})
    assert archived.status_code == 200
    assert _assignments(client, alice) == []
    ended = _assignment_history(client, alice)
    assert len(ended) == 1
    assert ended[0]["id"] == first["id"]
    assert ended[0]["effective_until"] is not None

    reactivated = client.patch(f"/policies/{policy['id']}", json={"status": "active"})
    assert reactivated.status_code == 200
    active = _assignments(client, alice)
    assert len(active) == 1
    assert active[0]["value"] == "blue"
    assert active[0]["id"] != first["id"]


def test_group_linked_policy_version_and_archive_reconcile_members_despite_conditions(
    client, db
):
    field = _create_field(client, "badge")
    policy = _create_policy(
        client,
        field,
        name="Engineering badge",
        condition_field="state",
        condition_value="Wisconsin",
        value="engineer",
        effective_from=current_date() - timedelta(days=1),
    )
    alice = _create_employee(client, "Alice", "California")
    group = client.post("/groups", json={"name": "Engineering"}).json()
    assert client.post(f"/groups/{group['id']}/employees/{alice['id']}").status_code == 201
    assert client.post(f"/groups/{group['id']}/policies/{policy['id']}").status_code == 201
    assert [item["value"] for item in _assignments(client, alice)] == ["engineer"]
    assert _employee_policy_ids(db, alice) == [policy["id"]]

    version = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 10,
            "effective_from": current_date().isoformat(),
            "condition_group": _condition("state", "Wisconsin"),
            "values": [{"assignment_field_definition_id": field["id"], "value": "senior"}],
        },
    )
    assert version.status_code == 201
    assert [item["value"] for item in _assignments(client, alice)] == ["senior"]
    assert _employee_policy_ids(db, alice) == [policy["id"]]

    assert client.patch(
        f"/policies/{policy['id']}", json={"status": "archived"}
    ).status_code == 200
    assert _assignments(client, alice) == []
    assert _employee_policy_ids(db, alice) == []


def test_future_group_policy_is_not_a_current_employee_policy_or_assignment(client, db):
    field = _create_field(client, "badge")
    policy = _create_policy(
        client,
        field,
        name="Future Engineering badge",
        condition_field="state",
        condition_value="Wisconsin",
        value="future",
        effective_from=current_date() + timedelta(days=1),
    )
    alice = _create_employee(client, "Alice", "California")
    group = client.post("/groups", json={"name": "Engineering"}).json()
    assert client.post(f"/groups/{group['id']}/employees/{alice['id']}").status_code == 201
    assert client.post(f"/groups/{group['id']}/policies/{policy['id']}").status_code == 201

    assert _employee_policy_ids(db, alice) == []
    assert _assignments(client, alice) == []
    assert _assignment_history(client, alice) == []


def test_conflicting_policy_creation_rolls_back_policy_audits_and_partial_fanout(
    client,
):
    field = _create_field(client)
    existing = _create_policy(
        client,
        field,
        name="Bob weekly",
        condition_field="name",
        condition_value="Bob",
        value="weekly",
    )
    alice = _create_employee(client, "Alice", "California")
    bob = _create_employee(client, "Bob", "California")
    bob_original = _assignments(client, bob)[0]
    audits_before = _audit_logs(client)

    response = client.post(
        "/policies",
        headers={"X-Actor": "admin_42"},
        json={
            "name": "California monthly",
            "priority": 10,
            "condition_group": _condition("state", "California"),
            "values": [{"assignment_field_definition_id": field["id"], "value": "monthly"}],
        },
    )
    assert response.status_code == 409
    assert "Conflicting values" in response.json()["detail"]

    assert [(item["id"], item["name"]) for item in client.get("/policies").json()] == [
        (existing["id"], "Bob weekly")
    ]
    assert _assignments(client, alice) == []
    assert _assignment_history(client, alice) == []
    assert _assignments(client, bob) == [bob_original]
    assert _assignment_history(client, bob) == [bob_original]
    assert _audit_logs(client) == audits_before


def test_conflicting_new_version_rolls_back_version_range_audits_and_partial_fanout(
    client,
):
    field = _create_field(client)
    changing = _create_policy(
        client,
        field,
        name="Changing payroll",
        condition_field="name",
        condition_value="Alice",
        value="monthly",
        effective_from=current_date() - timedelta(days=1),
    )
    _create_policy(
        client,
        field,
        name="Bob weekly",
        condition_field="name",
        condition_value="Bob",
        value="weekly",
    )
    alice = _create_employee(client, "Alice", "California")
    bob = _create_employee(client, "Bob", "California")
    alice_original = _assignments(client, alice)[0]
    bob_original = _assignments(client, bob)[0]
    audits_before = _audit_logs(client)

    response = client.post(
        f"/policies/{changing['id']}/versions",
        headers={"X-Actor": "admin_42"},
        json={
            "priority": 10,
            "effective_from": current_date().isoformat(),
            "condition_group": _condition("state", "California"),
            "values": [{"assignment_field_definition_id": field["id"], "value": "monthly"}],
        },
    )
    assert response.status_code == 409
    assert "Conflicting values" in response.json()["detail"]

    versions = client.get(f"/policies/{changing['id']}/versions").json()
    assert len(versions) == 1
    assert versions[0]["id"] == changing["versions"][0]["id"]
    assert versions[0]["effective_until"] is None
    assert _assignments(client, alice) == [alice_original]
    assert _assignment_history(client, alice) == [alice_original]
    assert _assignments(client, bob) == [bob_original]
    assert _assignment_history(client, bob) == [bob_original]
    assert _audit_logs(client) == audits_before
