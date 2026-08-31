from datetime import date, timedelta

from sqlalchemy import select

from app.dates import current_date, start_of_day
from app.models import ScheduledReconciliation
from app.services.condition_fields import add_calendar_years
from app.services.policy_matching import find_matching_policy_ids
from app.services.scheduled_reconciliations import (
    EMPLOYEE_ENTITY,
    TENURE_THRESHOLD_TRIGGER,
    reconcile_due_events,
)


def _create_assignment_field(client):
    response = client.post(
        "/assignment-fields",
        json={"name": "vacation", "cardinality": "one"},
    )
    assert response.status_code == 201
    return response.json()


def _create_tenure_policy(
    client,
    assignment_field_definition_id: int,
    *,
    operator: str = ">=",
    value: str = "1 year",
    effective_from: date | None = None,
):
    response = client.post(
        "/policies",
        json={
            "name": f"Tenure {operator} {value}",
            "priority": 10,
            "effective_from": (effective_from or current_date()).isoformat(),
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "tenure", "operator": operator, "value": value}
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": assignment_field_definition_id,
                    "value": "4 weeks",
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_employee(client, *, start_date: date):
    response = client.post(
        "/employees",
        json={
            "name": "Alice",
            "state": "California",
            "department": "Engineering",
            "employee_type": "regular",
            "start_date": start_date.isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


def _employee_tenure_events(db, employee_id: int):
    return list(
        db.scalars(
            select(ScheduledReconciliation)
            .where(
                ScheduledReconciliation.entity_type == EMPLOYEE_ENTITY,
                ScheduledReconciliation.entity_id == employee_id,
                ScheduledReconciliation.trigger_type == TENURE_THRESHOLD_TRIGGER,
            )
            .order_by(ScheduledReconciliation.scheduled_at, ScheduledReconciliation.id)
        )
    )


def test_condition_field_catalog_exposes_static_derived_and_dependency_metadata(client):
    response = client.get("/condition-fields")

    assert response.status_code == 200
    fields = {item["key"]: item for item in response.json()}
    assert fields["state"]["field_type"] == "static"
    assert fields["state"]["source_column"] == "state"
    assert fields["tenure"]["field_type"] == "derived"
    assert fields["tenure"]["data_type"] == "calendar_duration"
    assert fields["tenure"]["resolver_key"] == "employee_tenure_v1"
    assert {
        (item["dependency_type"], item["dependency_key"], item["impact_resolver_key"])
        for item in fields["tenure"]["dependencies"]
    } == {
        ("column", "employee.start_date", "changed_employee"),
        ("time", "evaluation_date", "tenure_threshold_schedule"),
    }


def test_tenure_input_is_typed_normalized_and_rejects_unknown_fields(client, db):
    field = _create_assignment_field(client)
    policy = _create_tenure_policy(client, field["id"], value="2 years")
    condition = policy["versions"][0]
    assert condition["version_number"] == 1

    invalid_duration = client.post(
        "/policies",
        json={
            "name": "Invalid tenure",
            "priority": 10,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "tenure", "operator": ">=", "value": "18 months"}
                ],
            },
        },
    )
    assert invalid_duration.status_code == 422

    unknown_field = client.post(
        "/policies",
        json={
            "name": "Unknown fact",
            "priority": 10,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "favorite_color", "operator": "=", "value": "blue"}
                ],
            },
        },
    )
    assert unknown_field.status_code == 422

    # The human input is persisted in its canonical calendar-duration form.
    from app.models import CompiledPolicyCondition

    stored = db.scalar(select(CompiledPolicyCondition))
    assert stored is not None
    assert stored.field == "tenure"
    assert stored.value == "P2Y"


def test_tenure_matches_before_and_on_the_calendar_anniversary(client, db):
    field = _create_assignment_field(client)
    policy = _create_tenure_policy(
        client,
        field["id"],
        value="2 years",
        effective_from=date(2020, 1, 1),
    )
    employee = _create_employee(client, start_date=date(2024, 1, 1))

    assert find_matching_policy_ids(db, employee["id"], date(2025, 12, 31)) == []
    assert find_matching_policy_ids(db, employee["id"], date(2026, 1, 1)) == [
        policy["id"]
    ]


def test_february_29_tenure_anniversary_is_february_28(client, db):
    assert add_calendar_years(date(2024, 2, 29), 1) == date(2025, 2, 28)
    field = _create_assignment_field(client)
    policy = _create_tenure_policy(
        client,
        field["id"],
        effective_from=date(2020, 1, 1),
    )
    employee = _create_employee(client, start_date=date(2024, 2, 29))

    assert find_matching_policy_ids(db, employee["id"], date(2025, 2, 27)) == []
    assert find_matching_policy_ids(db, employee["id"], date(2025, 2, 28)) == [
        policy["id"]
    ]


def test_employee_creation_schedules_threshold_and_due_event_changes_assignment(
    client,
    session_factory,
):
    today = current_date()
    field = _create_assignment_field(client)
    _create_tenure_policy(client, field["id"])
    employee = _create_employee(client, start_date=today)
    threshold = add_calendar_years(today, 1)

    with session_factory() as session:
        events = _employee_tenure_events(session, employee["id"])
        assert [(event.status, event.scheduled_at) for event in events] == [
            ("pending", start_of_day(threshold))
        ]

    assert client.get(f"/employees/{employee['id']}/assignments").json() == []
    with session_factory.begin() as session:
        processed = reconcile_due_events(session, as_of=start_of_day(threshold))
        assert len(processed) == 1

    assignments = client.get(
        f"/employees/{employee['id']}/assignments",
        params={"as_of": start_of_day(threshold).isoformat()},
    ).json()
    assert [item["value"] for item in assignments] == ["4 weeks"]


def test_start_date_and_policy_status_resynchronize_pending_tenure_events(
    client,
    session_factory,
):
    today = current_date()
    field = _create_assignment_field(client)
    policy = _create_tenure_policy(client, field["id"], value="2 years")
    original_start = add_calendar_years(today, -1)
    employee = _create_employee(client, start_date=original_start)
    original_threshold = add_calendar_years(original_start, 2)
    replacement_threshold = add_calendar_years(today, 2)

    response = client.patch(
        f"/employees/{employee['id']}",
        json={"start_date": today.isoformat()},
    )
    assert response.status_code == 200
    with session_factory() as session:
        events = _employee_tenure_events(session, employee["id"])
        assert [(event.status, event.scheduled_at) for event in events] == [
            ("cancelled", start_of_day(original_threshold)),
            ("pending", start_of_day(replacement_threshold)),
        ]

    assert client.patch(
        f"/policies/{policy['id']}", json={"status": "archived"}
    ).status_code == 200
    with session_factory() as session:
        assert [
            event.status for event in _employee_tenure_events(session, employee["id"])
        ] == ["cancelled", "cancelled"]

    assert client.patch(
        f"/policies/{policy['id']}", json={"status": "active"}
    ).status_code == 200
    with session_factory() as session:
        events = _employee_tenure_events(session, employee["id"])
        assert [(event.status, event.scheduled_at) for event in events] == [
            ("cancelled", start_of_day(original_threshold)),
            ("pending", start_of_day(replacement_threshold)),
        ]


def test_tenure_equality_schedules_entry_and_exit_boundaries(client, db):
    today = current_date()
    field = _create_assignment_field(client)
    _create_tenure_policy(client, field["id"], operator="=", value="1 year")
    employee = _create_employee(client, start_date=today)

    events = _employee_tenure_events(db, employee["id"])
    assert [(event.status, event.scheduled_at) for event in events] == [
        ("pending", start_of_day(add_calendar_years(today, 1))),
        ("pending", start_of_day(add_calendar_years(today, 2))),
    ]


def test_new_policy_version_replaces_obsolete_employee_tenure_schedule(client, db):
    today = current_date()
    field = _create_assignment_field(client)
    policy = _create_tenure_policy(client, field["id"], value="2 years")
    employee = _create_employee(client, start_date=today)
    old_threshold = add_calendar_years(today, 2)
    new_threshold = add_calendar_years(today, 3)

    response = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 10,
            "effective_from": (today + timedelta(days=30)).isoformat(),
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "tenure", "operator": ">=", "value": "3 years"}
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": field["id"],
                    "value": "5 weeks",
                }
            ],
        },
    )
    assert response.status_code == 201

    events = _employee_tenure_events(db, employee["id"])
    assert [(event.status, event.scheduled_at) for event in events] == [
        ("cancelled", start_of_day(old_threshold)),
        ("pending", start_of_day(new_threshold)),
    ]
