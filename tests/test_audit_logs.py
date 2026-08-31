from datetime import timedelta

from sqlalchemy import select

from app.dates import current_date
from app.models import AuditLog, Group
from app.services.audit import record_audit_log, snapshot_entity


def _condition_group(state: str = "Wisconsin") -> dict:
    return {
        "logical_operator": "and",
        "conditions": [{"field": "state", "operator": "=", "value": state}],
    }


def _create_field(client, name: str = "pay_schedule") -> dict:
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": "one"},
    )
    assert response.status_code == 201
    return response.json()


def _create_employee(client) -> dict:
    response = client.post(
        "/employees",
        json={
            "name": "Alice",
            "state": "California",
            "department": "Engineering",
            "employee_type": "regular",
        },
    )
    assert response.status_code == 201
    return response.json()


def _audit_logs(client, **params) -> list[dict]:
    response = client.get(
        "/audit-logs",
        headers={"X-Audit-Key": "test-audit-key"},
        params=params,
    )
    assert response.status_code == 200
    return response.json()


def test_policy_and_version_audits_include_actor_and_version_snapshots(client, monkeypatch):
    monkeypatch.setenv("AUDIT_ADMIN_KEY", "test-audit-key")
    field = _create_field(client)
    headers = {"X-Actor": "admin_42"}
    today = current_date()
    first = client.post(
        "/policies",
        headers=headers,
        json={
            "name": "Pay schedule",
            "priority": 10,
            "effective_from": today.isoformat(),
            "condition_group": _condition_group("California"),
            "values": [{"assignment_field_definition_id": field["id"], "value": "weekly"}],
        },
    )
    assert first.status_code == 201
    policy = first.json()

    second_start = today + timedelta(days=30)
    second = client.post(
        f"/policies/{policy['id']}/versions",
        headers=headers,
        json={
            "priority": 20,
            "effective_from": second_start.isoformat(),
            "condition_group": _condition_group("California"),
            "values": [{"assignment_field_definition_id": field["id"], "value": "biweekly"}],
        },
    )
    assert second.status_code == 201
    assert client.patch(
        f"/policies/{policy['id']}",
        headers=headers,
        json={"status": "archived"},
    ).status_code == 200

    policy_events = _audit_logs(
        client,
        entity_type="Policy",
        entity_id=policy["id"],
    )
    assert [(event["actor"], event["action"]) for event in policy_events] == [
        ("admin_42", "created"),
        ("admin_42", "archived"),
    ]
    assert policy_events[0]["before"] is None
    assert policy_events[0]["after"]["name"] == "Pay schedule"
    assert policy_events[1]["before"]["status"] == "active"
    assert policy_events[1]["after"]["status"] == "archived"

    version_events = _audit_logs(client, entity_type="PolicyVersion", actor="admin_42")
    assert len(version_events) == 2
    assert version_events[0]["before"] is None
    assert version_events[0]["after"]["version_number"] == 1
    assert version_events[1]["before"]["version_number"] == 1
    assert version_events[1]["before"]["effective_until"] is None
    assert version_events[1]["after"]["version_number"] == 2
    assert version_events[1]["after"]["values"] == [
        {"assignment_field_definition_id": field["id"], "value": "biweekly"}
    ]


def test_group_membership_policy_and_assignment_audits_are_material_only(client, monkeypatch):
    monkeypatch.setenv("AUDIT_ADMIN_KEY", "test-audit-key")
    field = _create_field(client, "badge")
    policy = client.post(
        "/policies",
        json={
            "name": "Engineering badge",
            "priority": 10,
            "condition_group": _condition_group(),
            "values": [{"assignment_field_definition_id": field["id"], "value": "engineer"}],
        },
    ).json()
    employee = _create_employee(client)
    headers = {"X-Actor": "admin_7"}
    group = client.post("/groups", headers=headers, json={"name": "Engineering"}).json()
    assert client.patch(
        f"/groups/{group['id']}", headers=headers, json={"name": "Platform"}
    ).status_code == 200
    assert client.post(
        f"/groups/{group['id']}/employees/{employee['id']}", headers=headers
    ).status_code == 201
    # Repeating a membership mutation is a no-op and must not add an audit row.
    assert client.post(
        f"/groups/{group['id']}/employees/{employee['id']}", headers=headers
    ).status_code == 201
    assert client.post(
        f"/groups/{group['id']}/policies/{policy['id']}", headers=headers
    ).status_code == 201
    # Reconciliation with an unchanged result must not emit assignment events.
    assert client.post(f"/employees/{employee['id']}/refresh").status_code == 200
    assert client.delete(
        f"/groups/{group['id']}/employees/{employee['id']}", headers=headers
    ).status_code == 204
    assert client.delete(
        f"/groups/{group['id']}/policies/{policy['id']}", headers=headers
    ).status_code == 204

    group_events = _audit_logs(client, entity_type="Group", entity_id=group["id"])
    assert [event["action"] for event in group_events] == [
        "created",
        "changed",
        "employee_added",
        "policy_attached",
        "employee_removed",
        "policy_detached",
    ]
    assert all(event["actor"] == "admin_7" for event in group_events)

    assignment_events = _audit_logs(
        client,
        entity_type="EmployeeAssignment",
        entity_id=1,
    )
    assert [event["action"] for event in assignment_events] == ["created", "ended"]
    assert all(event["actor"] == "system" for event in assignment_events)
    assert assignment_events[0]["after"]["field"] == "badge"
    assert assignment_events[0]["after"]["value"] == "engineer"
    assert assignment_events[1]["before"]["value"] == "engineer"
    assert assignment_events[1]["after"] is None


def test_override_lifecycle_audits_override_and_assignment_replacement(client, monkeypatch):
    monkeypatch.setenv("AUDIT_ADMIN_KEY", "test-audit-key")
    field = _create_field(client)
    employee = _create_employee(client)
    headers = {"X-Actor": "admin_9"}

    created = client.post(
        f"/employees/{employee['id']}/overrides",
        headers=headers,
        json={"assignment_field_definition_id": field["id"], "value": "weekly"},
    )
    assert created.status_code == 201
    first_override = created.json()
    changed = client.patch(
        f"/employees/{employee['id']}/overrides/{first_override['id']}",
        headers=headers,
        json={"value": "biweekly"},
    )
    assert changed.status_code == 200
    replacement = changed.json()
    assert client.delete(
        f"/employees/{employee['id']}/overrides/{replacement['id']}",
        headers=headers,
    ).status_code == 204

    override_events = _audit_logs(client, entity_type="EmployeeOverride")
    assert [event["action"] for event in override_events] == [
        "created",
        "changed",
        "removed",
    ]
    assert all(event["actor"] == "admin_9" for event in override_events)
    assert override_events[1]["before"]["value"] == "weekly"
    assert override_events[1]["after"]["value"] == "biweekly"
    assert override_events[2]["before"]["value"] == "biweekly"
    assert override_events[2]["after"] is None

    assignment_events = _audit_logs(client, entity_type="EmployeeAssignment")
    assert [event["action"] for event in assignment_events] == [
        "created",
        "ended",
        "created",
        "ended",
    ]
    assert all(event["actor"] == "system" for event in assignment_events)


def test_audit_read_endpoint_requires_configured_admin_key(client, monkeypatch):
    monkeypatch.delenv("AUDIT_ADMIN_KEY", raising=False)
    assert client.get("/audit-logs").status_code == 503

    monkeypatch.setenv("AUDIT_ADMIN_KEY", "right-key")
    assert client.get("/audit-logs", headers={"X-Audit-Key": "wrong-key"}).status_code == 403
    assert client.get("/audit-logs", headers={"X-Audit-Key": "right-key"}).status_code == 200


def test_audit_rows_share_the_domain_transaction(session_factory):
    with session_factory() as session:
        group = Group(name="Temporary")
        session.add(group)
        session.flush()
        assert snapshot_entity(group, redact={"name"})["name"] == "[REDACTED]"
        record_audit_log(
            session,
            actor="admin_1",
            entity_type="Group",
            entity_id=group.id,
            action="created",
            before=None,
            after=snapshot_entity(group),
        )
        session.rollback()

    with session_factory() as session:
        assert session.scalars(select(Group)).all() == []
        assert session.scalars(select(AuditLog)).all() == []


def test_failed_reconciliation_rolls_back_causal_and_assignment_audits(client, monkeypatch):
    monkeypatch.setenv("AUDIT_ADMIN_KEY", "test-audit-key")
    field = _create_field(client)

    def create_policy(name: str, value: str) -> dict:
        response = client.post(
            "/policies",
            json={
                "name": name,
                "priority": 10,
                "condition_group": _condition_group(),
                "values": [
                    {"assignment_field_definition_id": field["id"], "value": value}
                ],
            },
        )
        assert response.status_code == 201
        return response.json()

    weekly = create_policy("Weekly", "weekly")
    monthly = create_policy("Monthly", "monthly")
    employee = _create_employee(client)
    group = client.post("/groups", json={"name": "Engineering"}).json()
    client.post(f"/groups/{group['id']}/employees/{employee['id']}")
    assert client.post(
        f"/groups/{group['id']}/policies/{weekly['id']}"
    ).status_code == 201

    failed = client.post(f"/groups/{group['id']}/policies/{monthly['id']}")
    assert failed.status_code == 409

    group_events = _audit_logs(client, entity_type="Group", entity_id=group["id"])
    assert [event["action"] for event in group_events].count("policy_attached") == 1
    assignment_events = _audit_logs(client, entity_type="EmployeeAssignment")
    assert [event["action"] for event in assignment_events] == ["created"]
    assert assignment_events[0]["after"]["value"] == "weekly"
