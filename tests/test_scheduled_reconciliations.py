from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.dates import current_date, start_of_day
from app.models import Employee, EmployeeOverride, FieldDefinition, ScheduledReconciliation
from app.services.policy_engine import PolicyConflictError
from app.services.scheduled_reconciliations import (
    BECOMES_EFFECTIVE_TRIGGER,
    EMPLOYEE_ENTITY,
    EMPLOYEE_OVERRIDE_ENTITY,
    EXPIRES_TRIGGER,
    POLICY_VERSION_ENTITY,
    TENURE_THRESHOLD_TRIGGER,
    cancel_pending_reconciliations,
    get_due_reconciliations,
    reconcile_due_events,
    schedule_reconciliation,
)


def _condition(state="California"):
    return {
        "logical_operator": "and",
        "conditions": [{"field": "state", "operator": "=", "value": state}],
    }


def _create_field(client, name="pay_schedule"):
    response = client.post(
        "/field-definitions",
        json={"name": name, "cardinality": "one"},
    )
    assert response.status_code == 201
    return response.json()


def _create_employee(client, state="California"):
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


def _create_policy(
    client,
    field_id,
    *,
    value="weekly",
    priority=10,
    state="California",
    effective_from=None,
    effective_until=None,
):
    body = {
        "name": f"{state} {value}",
        "priority": priority,
        "condition_group": _condition(state),
        "values": [{"field_definition_id": field_id, "value": value}],
    }
    if effective_from is not None:
        body["effective_from"] = effective_from.isoformat()
    if effective_until is not None:
        body["effective_until"] = effective_until.isoformat()
    response = client.post("/policies", json=body)
    assert response.status_code == 201
    return response.json()


def _events(db):
    db.expire_all()
    return list(
        db.scalars(
            select(ScheduledReconciliation).order_by(
                ScheduledReconciliation.scheduled_at,
                ScheduledReconciliation.id,
            )
        )
    )


def test_generic_scheduling_is_idempotent_filterable_and_cancellable(db):
    due_at = datetime(2027, 4, 15, tzinfo=UTC)
    first = schedule_reconciliation(
        db,
        entity_type=EMPLOYEE_ENTITY,
        entity_id=100,
        trigger_type=TENURE_THRESHOLD_TRIGGER,
        scheduled_at=due_at,
    )
    duplicate = schedule_reconciliation(
        db,
        entity_type=EMPLOYEE_ENTITY,
        entity_id=100,
        trigger_type=TENURE_THRESHOLD_TRIGGER,
        scheduled_at=due_at,
    )
    later = schedule_reconciliation(
        db,
        entity_type=EMPLOYEE_ENTITY,
        entity_id=100,
        trigger_type=TENURE_THRESHOLD_TRIGGER,
        scheduled_at=due_at + timedelta(days=1),
    )

    assert duplicate.id == first.id
    assert [event.id for event in get_due_reconciliations(db, as_of=due_at)] == [
        first.id
    ]
    cancelled = cancel_pending_reconciliations(
        db,
        entity_type=EMPLOYEE_ENTITY,
        entity_ids=[100],
        keep=[(100, TENURE_THRESHOLD_TRIGGER, later.scheduled_at)],
    )
    assert [event.id for event in cancelled] == [first.id]
    assert get_due_reconciliations(db, as_of=due_at) == []

    restored = schedule_reconciliation(
        db,
        entity_type=EMPLOYEE_ENTITY,
        entity_id=100,
        trigger_type=TENURE_THRESHOLD_TRIGGER,
        scheduled_at=due_at,
    )
    assert restored.id == first.id
    assert restored.status == "pending"


def test_policy_creation_schedules_future_activation_and_inclusive_expiration(client, db):
    field = _create_field(client)
    starts = current_date() + timedelta(days=10)
    ends = starts + timedelta(days=5)
    policy = _create_policy(
        client,
        field["id"],
        effective_from=starts,
        effective_until=ends,
    )
    version_id = policy["versions"][0]["id"]

    events = _events(db)
    assert [
        (event.entity_type, event.entity_id, event.trigger_type, event.scheduled_at)
        for event in events
    ] == [
        (
            POLICY_VERSION_ENTITY,
            version_id,
            BECOMES_EFFECTIVE_TRIGGER,
            start_of_day(starts).replace(tzinfo=None),
        ),
        (
            POLICY_VERSION_ENTITY,
            version_id,
            EXPIRES_TRIGGER,
            start_of_day(ends + timedelta(days=1)).replace(tzinfo=None),
        ),
    ]


def test_new_versions_schedule_both_sides_of_each_effective_boundary(client, db):
    field = _create_field(client)
    policy = _create_policy(
        client,
        field["id"],
        effective_from=current_date() - timedelta(days=1),
    )
    first_id = policy["versions"][0]["id"]
    second_start = current_date() + timedelta(days=10)
    second = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 10,
            "effective_from": second_start.isoformat(),
            "condition_group": _condition(),
            "values": [{"field_definition_id": field["id"], "value": "biweekly"}],
        },
    )
    assert second.status_code == 201

    events = _events(db)
    assert [
        (event.entity_id, event.trigger_type, event.scheduled_at)
        for event in events
    ] == [
        (
            first_id,
            EXPIRES_TRIGGER,
            start_of_day(second_start).replace(tzinfo=None),
        ),
        (
            second.json()["id"],
            BECOMES_EFFECTIVE_TRIGGER,
            start_of_day(second_start).replace(tzinfo=None),
        ),
    ]


def test_archiving_cancels_and_reactivation_restores_future_events(client, db):
    field = _create_field(client)
    starts = current_date() + timedelta(days=10)
    policy = _create_policy(
        client,
        field["id"],
        effective_from=starts,
    )
    original = _events(db)
    assert len(original) == 1
    original_id = original[0].id

    assert client.patch(
        f"/policies/{policy['id']}", json={"status": "archived"}
    ).status_code == 200
    assert [(event.id, event.status) for event in _events(db)] == [
        (original_id, "cancelled")
    ]

    assert client.patch(
        f"/policies/{policy['id']}", json={"status": "active"}
    ).status_code == 200
    assert [(event.id, event.status) for event in _events(db)] == [
        (original_id, "pending")
    ]


def test_due_policy_events_activate_then_expire_assignments(
    client,
    session_factory,
):
    field = _create_field(client)
    alice = _create_employee(client)
    starts = current_date() + timedelta(days=1)
    policy = _create_policy(
        client,
        field["id"],
        effective_from=starts,
        effective_until=starts,
    )
    assert client.get(f"/employees/{alice['id']}/assignments").json() == []

    activation_run = start_of_day(starts) + timedelta(hours=1)
    with session_factory.begin() as session:
        processed = reconcile_due_events(session, as_of=activation_run)
        assert [(event.trigger_type, event.status) for event in processed] == [
            (BECOMES_EFFECTIVE_TRIGGER, "processed")
        ]
    assignments = client.get(
        f"/employees/{alice['id']}/assignments",
        params={"as_of": activation_run.isoformat()},
    ).json()
    assert [(item["value"], item["source_policy_version_id"]) for item in assignments] == [
        ("weekly", policy["versions"][0]["id"])
    ]

    expiration_run = start_of_day(starts + timedelta(days=1)) + timedelta(hours=1)
    with session_factory.begin() as session:
        processed = reconcile_due_events(session, as_of=expiration_run)
        assert [(event.trigger_type, event.status) for event in processed] == [
            (EXPIRES_TRIGGER, "processed")
        ]
    assert client.get(
        f"/employees/{alice['id']}/assignments",
        params={"as_of": expiration_run.isoformat()},
    ).json() == []


def test_same_policy_boundary_events_reconcile_policy_once(
    client,
    session_factory,
    monkeypatch,
):
    field = _create_field(client)
    _create_employee(client)
    policy = _create_policy(
        client,
        field["id"],
        effective_from=current_date() - timedelta(days=1),
    )
    starts = current_date() + timedelta(days=1)
    response = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 20,
            "effective_from": starts.isoformat(),
            "condition_group": _condition(),
            "values": [{"field_definition_id": field["id"], "value": "biweekly"}],
        },
    )
    assert response.status_code == 201

    from app.services import scheduled_reconciliations as service

    original = service.refresh_employees_affected_by_policy
    calls = []

    def track_refresh(session, changed_policy, reconciliation_at=None):
        calls.append(changed_policy.id)
        return original(session, changed_policy, reconciliation_at)

    monkeypatch.setattr(service, "refresh_employees_affected_by_policy", track_refresh)
    with session_factory.begin() as session:
        processed = reconcile_due_events(
            session,
            as_of=start_of_day(starts) + timedelta(hours=1),
        )

    assert len(processed) == 2
    assert calls == [policy["id"]]


def test_employee_trigger_uses_the_shared_employee_reconciliation_path(
    client,
    session_factory,
):
    field = _create_field(client, "badge")
    _create_policy(client, field["id"], state="Wisconsin", value="blue")
    alice = _create_employee(client, state="California")
    due_at = datetime(2027, 4, 15, tzinfo=UTC)

    with session_factory.begin() as session:
        employee = session.get(Employee, alice["id"])
        assert employee is not None
        employee.state = "Wisconsin"
        schedule_reconciliation(
            session,
            entity_type=EMPLOYEE_ENTITY,
            entity_id=alice["id"],
            trigger_type=TENURE_THRESHOLD_TRIGGER,
            scheduled_at=due_at,
        )
    with session_factory.begin() as session:
        reconcile_due_events(session, as_of=due_at)

    assert [
        item["value"]
        for item in client.get(
            f"/employees/{alice['id']}/assignments",
            params={"as_of": due_at.isoformat()},
        ).json()
    ] == ["blue"]


def test_override_trigger_dispatches_assignment_reconciliation(
    session_factory,
    monkeypatch,
):
    due_at = datetime(2027, 9, 1, tzinfo=UTC)
    with session_factory.begin() as session:
        employee = Employee(
            name="Alice",
            state="California",
            department="Engineering",
            employee_type="regular",
        )
        field = FieldDefinition(name="pay_schedule", cardinality="one")
        override = EmployeeOverride(
            employee=employee,
            field_definition=field,
            value="monthly",
        )
        session.add(override)
        session.flush()
        override_id = override.id
        employee_id = employee.id
        schedule_reconciliation(
            session,
            entity_type=EMPLOYEE_OVERRIDE_ENTITY,
            entity_id=override_id,
            trigger_type=EXPIRES_TRIGGER,
            scheduled_at=due_at,
        )

    from app.services import scheduled_reconciliations as service

    calls = []

    def track_refresh(session, employee, evaluation_date, reconciliation_at):
        calls.append((employee.id, evaluation_date, reconciliation_at))
        return []

    monkeypatch.setattr(service, "refresh_employee_assignments", track_refresh)
    with session_factory.begin() as session:
        processed = reconcile_due_events(session, as_of=due_at)

    assert len(processed) == 1
    assert calls == [(employee_id, due_at.date(), due_at)]


def test_failed_due_reconciliation_rolls_back_and_leaves_event_pending(
    client,
    session_factory,
):
    field = _create_field(client)
    alice = _create_employee(client)
    _create_policy(client, field["id"], value="monthly", priority=10)
    original = client.get(f"/employees/{alice['id']}/assignments").json()
    starts = current_date() + timedelta(days=1)
    _create_policy(
        client,
        field["id"],
        value="weekly",
        priority=10,
        effective_from=starts,
    )

    with pytest.raises(PolicyConflictError, match="Conflicting values"):
        with session_factory.begin() as session:
            reconcile_due_events(
                session,
                as_of=start_of_day(starts) + timedelta(hours=1),
            )

    with session_factory() as session:
        events = list(session.scalars(select(ScheduledReconciliation)))
        assert [(event.status, event.processed_at) for event in events] == [
            ("pending", None)
        ]
    assert client.get(f"/employees/{alice['id']}/assignments").json() == original
