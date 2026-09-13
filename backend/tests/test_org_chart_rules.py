from __future__ import annotations

from app.models import Employee
from app.services.org_chart import get_ancestor_ids, get_descendant_ids


def _employee(
    client,
    name: str,
    *,
    manager_id: int | None = None,
    state: str = "California",
) -> dict:
    payload = {
        "name": name,
        "state": state,
        "department": "Engineering",
        "employee_type": "regular",
    }
    if manager_id is not None:
        payload["manager_id"] = manager_id
    response = client.post("/employees", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def _field(client, name: str) -> dict:
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": "one"},
    )
    assert response.status_code == 201
    return response.json()


def _policy(
    client,
    *,
    name: str,
    condition_field: str,
    operator: str,
    condition_value: str,
    assignment_field_id: int,
    assignment_value: str,
    priority: int = 10,
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
                        "operator": operator,
                        "value": condition_value,
                    }
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": assignment_field_id,
                    "value": assignment_value,
                }
            ],
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def _assignments(client, employee_id: int) -> dict[str, str]:
    response = client.get(f"/employees/{employee_id}/assignments")
    assert response.status_code == 200
    return {
        item["assignment_field_definition"]["name"]: item["value"]
        for item in response.json()
    }


def test_employee_manager_is_a_real_self_referencing_relationship(db):
    manager = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    report = Employee(
        name="Bob",
        state="California",
        department="Engineering",
        employee_type="regular",
        manager=manager,
    )
    db.add_all([manager, report])
    db.flush()

    assert report.manager is manager
    assert manager.direct_reports == [report]
    assert report.manager_id == manager.id


def test_org_chart_queries_walk_ancestors_and_descendants(db):
    alice = Employee(
        name="Alice", state="CA", department="Eng", employee_type="regular"
    )
    bob = Employee(
        name="Bob", state="CA", department="Eng", employee_type="regular", manager=alice
    )
    carol = Employee(
        name="Carol", state="CA", department="Eng", employee_type="regular", manager=bob
    )
    dana = Employee(
        name="Dana",
        state="CA",
        department="Eng",
        employee_type="regular",
        manager=alice,
    )
    db.add_all([alice, bob, carol, dana])
    db.flush()

    assert get_ancestor_ids(db, carol.id) == {alice.id, bob.id}
    assert get_descendant_ids(db, alice.id) == {bob.id, carol.id, dana.id}


def test_manager_validation_rejects_missing_self_and_cycles(client):
    missing = client.post(
        "/employees",
        json={
            "name": "Orphan",
            "state": "California",
            "department": "Engineering",
            "employee_type": "regular",
            "manager_id": 999,
        },
    )
    assert missing.status_code == 404

    alice = _employee(client, "Alice")
    bob = _employee(client, "Bob", manager_id=alice["id"])
    carol = _employee(client, "Carol", manager_id=bob["id"])

    self_managed = client.patch(
        f"/employees/{alice['id']}",
        json={"manager_id": alice["id"]},
    )
    assert self_managed.status_code == 409

    cycle = client.patch(
        f"/employees/{alice['id']}",
        json={"manager_id": carol["id"]},
    )
    assert cycle.status_code == 409
    assert client.get(f"/employees/{alice['id']}").json()["manager_id"] is None


def test_condition_catalog_declares_org_fields_and_dependencies(client):
    response = client.get("/condition-fields")
    assert response.status_code == 200
    fields = {item["key"]: item for item in response.json()}

    assert fields["employee_id"]["label"] == "Employee"
    assert fields["employee_id"]["data_type"] == "employee_reference"
    assert fields["employee_id"]["allowed_operators"] == ["="]
    assert fields["employee_id"]["input"]["type"] == "resource"
    assert fields["employee_id"]["input"]["reference_resource"] == "employees"
    assert fields["department"]["input"]["reference_resource"] == "departments"
    assert fields["employee_type"]["input"]["reference_resource"] == "employee_types"
    assert fields["manager_id"]["field_type"] == "static"
    assert fields["manager_id"]["data_type"] == "employee_reference"
    assert fields["manager_id"]["allowed_operators"] == ["="]
    assert fields["manager_id"]["input"]["type"] == "resource"
    assert fields["manager_id"]["input"]["reference_resource"] == "employees"
    assert fields["is_manager"]["resolver_key"] == "employee_is_manager_v1"
    assert fields["is_manager"]["allowed_operators"] == ["="]
    assert fields["is_manager"]["input"]["type"] == "select"
    assert fields["is_manager"]["input"]["options"] == [
        {"value": "true", "label": "True"},
        {"value": "false", "label": "False"},
    ]
    assert fields["direct_report_count"]["data_type"] == "integer"
    assert fields["direct_report_count"]["input"]["minimum"] == 0
    assert fields["reports_under"]["resolver_key"] == "employee_manager_chain_v1"
    assert fields["management_level"]["resolver_key"] == "employee_management_level_v1"
    assert {
        dependency["impact_resolver_key"]
        for key in (
            "is_manager",
            "direct_report_count",
            "reports_under",
            "management_level",
        )
        for dependency in fields[key]["dependencies"]
    } == {"old_and_new_managers", "moved_subtree"}


def test_all_org_chart_condition_types_match(client):
    alice = _employee(client, "Alice")
    bob = _employee(client, "Bob", manager_id=alice["id"])
    _employee(client, "Dana", manager_id=alice["id"])
    carol = _employee(client, "Carol", manager_id=bob["id"])

    manager_training = _field(client, "manager_training")
    large_team = _field(client, "large_team")
    direct_staff = _field(client, "direct_staff")
    hierarchy = _field(client, "hierarchy")
    deep_org = _field(client, "deep_org")
    employee_specific = _field(client, "employee_specific")

    _policy(
        client,
        name="Alice only",
        condition_field="employee_id",
        operator="=",
        condition_value=str(alice["id"]),
        assignment_field_id=employee_specific["id"],
        assignment_value="true",
    )

    _policy(
        client,
        name="Manager training",
        condition_field="is_manager",
        operator="=",
        condition_value="TRUE",
        assignment_field_id=manager_training["id"],
        assignment_value="required",
    )
    _policy(
        client,
        name="Large direct team",
        condition_field="direct_report_count",
        operator=">=",
        condition_value="2",
        assignment_field_id=large_team["id"],
        assignment_value="true",
    )
    _policy(
        client,
        name="Alice direct staff",
        condition_field="manager_id",
        operator="=",
        condition_value=str(alice["id"]),
        assignment_field_id=direct_staff["id"],
        assignment_value="true",
    )
    _policy(
        client,
        name="Alice hierarchy",
        condition_field="reports_under",
        operator="=",
        condition_value=str(alice["id"]),
        assignment_field_id=hierarchy["id"],
        assignment_value="alice",
    )
    _policy(
        client,
        name="Deep hierarchy",
        condition_field="management_level",
        operator=">=",
        condition_value="2",
        assignment_field_id=deep_org["id"],
        assignment_value="true",
    )

    alice_assignments = _assignments(client, alice["id"])
    bob_assignments = _assignments(client, bob["id"])
    carol_assignments = _assignments(client, carol["id"])

    assert alice_assignments == {
        "employee_specific": "true",
        "large_team": "true",
        "manager_training": "required",
    }
    assert bob_assignments == {
        "direct_staff": "true",
        "hierarchy": "alice",
        "manager_training": "required",
    }
    assert carol_assignments == {
        "deep_org": "true",
        "hierarchy": "alice",
    }


def test_manager_change_reconciles_old_new_managers_and_moved_subtree(client):
    alice = _employee(client, "Alice")
    eve = _employee(client, "Eve")
    david = _employee(client, "David", manager_id=eve["id"])
    bob = _employee(client, "Bob", manager_id=alice["id"])
    sarah = _employee(client, "Sarah", manager_id=bob["id"])

    manager_status = _field(client, "manager_status")
    team_lead = _field(client, "team_lead")
    hierarchy = _field(client, "org_hierarchy")
    deep_org = _field(client, "deep_org")
    _policy(
        client,
        name="Manager status",
        condition_field="is_manager",
        operator="=",
        condition_value="true",
        assignment_field_id=manager_status["id"],
        assignment_value="manager",
    )
    _policy(
        client,
        name="Team lead",
        condition_field="direct_report_count",
        operator=">=",
        condition_value="1",
        assignment_field_id=team_lead["id"],
        assignment_value="true",
    )
    _policy(
        client,
        name="Alice hierarchy",
        condition_field="reports_under",
        operator="=",
        condition_value=str(alice["id"]),
        assignment_field_id=hierarchy["id"],
        assignment_value="alice",
    )
    _policy(
        client,
        name="David hierarchy",
        condition_field="reports_under",
        operator="=",
        condition_value=str(david["id"]),
        assignment_field_id=hierarchy["id"],
        assignment_value="david",
    )
    _policy(
        client,
        name="Deep org",
        condition_field="management_level",
        operator=">=",
        condition_value="3",
        assignment_field_id=deep_org["id"],
        assignment_value="true",
    )

    assert _assignments(client, alice["id"])["manager_status"] == "manager"
    assert "manager_status" not in _assignments(client, david["id"])
    assert _assignments(client, alice["id"])["team_lead"] == "true"
    assert "team_lead" not in _assignments(client, david["id"])
    assert _assignments(client, bob["id"])["org_hierarchy"] == "alice"
    assert _assignments(client, sarah["id"])["org_hierarchy"] == "alice"
    assert "deep_org" not in _assignments(client, sarah["id"])

    changed = client.patch(
        f"/employees/{bob['id']}",
        headers={"X-Actor": "admin_42"},
        json={"manager_id": david["id"]},
    )
    assert changed.status_code == 200

    assert "manager_status" not in _assignments(client, alice["id"])
    assert _assignments(client, david["id"])["manager_status"] == "manager"
    assert "team_lead" not in _assignments(client, alice["id"])
    assert _assignments(client, david["id"])["team_lead"] == "true"
    assert _assignments(client, bob["id"])["org_hierarchy"] == "david"
    assert _assignments(client, sarah["id"])["org_hierarchy"] == "david"
    assert _assignments(client, sarah["id"])["deep_org"] == "true"


def test_manager_change_is_audited(client):
    alice = _employee(client, "Alice")
    david = _employee(client, "David")
    bob = _employee(client, "Bob", manager_id=alice["id"])

    response = client.patch(
        f"/employees/{bob['id']}",
        headers={"X-Actor": "admin_42"},
        json={"manager_id": david["id"]},
    )
    assert response.status_code == 200

    events = client.get(
        "/audit-logs",
        params={"entity_type": "Employee", "entity_id": bob["id"]},
    ).json()
    assert events[-1]["actor"] == "admin_42"
    assert events[-1]["action"] == "manager_changed"
    assert events[-1]["before"]["manager_id"] == alice["id"]
    assert events[-1]["after"]["manager_id"] == david["id"]


def test_deleting_manager_detaches_and_reconciles_reporting_subtree(client):
    alice = _employee(client, "Alice")
    bob = _employee(client, "Bob", manager_id=alice["id"])
    sarah = _employee(client, "Sarah", manager_id=bob["id"])
    hierarchy = _field(client, "hierarchy")
    _policy(
        client,
        name="Alice hierarchy",
        condition_field="reports_under",
        operator="=",
        condition_value=str(alice["id"]),
        assignment_field_id=hierarchy["id"],
        assignment_value="alice",
    )
    assert _assignments(client, sarah["id"])["hierarchy"] == "alice"

    deleted = client.delete(f"/employees/{bob['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/employees/{bob['id']}").status_code == 404
    assert client.get(f"/employees/{sarah['id']}").json()["manager_id"] is None
    assert _assignments(client, sarah["id"]) == {}


def test_manager_change_rolls_back_when_affected_manager_has_policy_conflict(client):
    field = _field(client, "schedule")
    alice = _employee(client, "Alice", state="California")
    david = _employee(client, "David", state="Texas")
    bob = _employee(client, "Bob", manager_id=alice["id"])
    _policy(
        client,
        name="Texas schedule",
        condition_field="state",
        operator="=",
        condition_value="Texas",
        assignment_field_id=field["id"],
        assignment_value="weekly",
        priority=10,
    )
    _policy(
        client,
        name="Manager schedule",
        condition_field="is_manager",
        operator="=",
        condition_value="true",
        assignment_field_id=field["id"],
        assignment_value="monthly",
        priority=10,
    )

    failed = client.patch(
        f"/employees/{bob['id']}",
        json={"manager_id": david["id"]},
    )
    assert failed.status_code == 409
    assert client.get(f"/employees/{bob['id']}").json()["manager_id"] == alice["id"]
    assert _assignments(client, alice["id"])["schedule"] == "monthly"
    assert _assignments(client, david["id"])["schedule"] == "weekly"


def test_employee_reference_conditions_require_an_existing_employee(client):
    field = _field(client, "hierarchy")
    response = client.post(
        "/policies",
        json={
            "name": "Missing leader",
            "priority": 10,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "reports_under", "operator": "=", "value": "999"}
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": field["id"],
                    "value": "missing",
                }
            ],
        },
    )
    assert response.status_code == 404
    assert client.get("/policies").json() == []
