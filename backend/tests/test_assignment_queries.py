from datetime import date, timedelta

from sqlalchemy import func, select

from app.dates import current_date
from app.models import AuditLog, EmployeeAssignment, EmployeePolicy


def _create_field(client, name: str = "vacation") -> dict:
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": "one"},
    )
    assert response.status_code == 201
    return response.json()


def _condition(field: str, value: str, operator: str = "=") -> dict:
    return {
        "logical_operator": "and",
        "conditions": [
            {"field": field, "operator": operator, "value": value}
        ],
    }


def _create_policy(
    client,
    field_id: int,
    *,
    condition_field: str = "state",
    condition_value: str = "CA",
    condition_operator: str = "=",
    value: str = "3 weeks",
    effective_from: date | None = None,
) -> dict:
    response = client.post(
        "/policies",
        json={
            "name": "Vacation",
            "priority": 10,
            "effective_from": (effective_from or current_date()).isoformat(),
            "condition_group": _condition(
                condition_field,
                condition_value,
                condition_operator,
            ),
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


def _create_employee(
    client,
    *,
    name: str = "Alice",
    state: str = "CA",
    start_date: date | None = None,
) -> dict:
    body = {
        "name": name,
        "state": state,
        "department": "Engineering",
        "employee_type": "regular",
    }
    if start_date is not None:
        body["start_date"] = start_date.isoformat()
    response = client.post("/employees", json=body)
    assert response.status_code == 201
    return response.json()


def _query(client, employee_ids: list[int], evaluation_date: date):
    return client.post(
        "/assignment-queries",
        json={
            "employee_ids": employee_ids,
            "evaluation_date": evaluation_date.isoformat(),
        },
    )


def _projection_counts(db) -> tuple[int, int, int]:
    return (
        db.scalar(select(func.count()).select_from(EmployeeAssignment)),
        db.scalar(select(func.count()).select_from(EmployeePolicy)),
        db.scalar(select(func.count()).select_from(AuditLog)),
    )


def test_query_uses_recorded_past_current_projection_and_future_resolution(client, db):
    today = current_date()
    future = today + timedelta(days=30)
    field = _create_field(client)
    policy = _create_policy(client, field["id"])
    employee = _create_employee(client)
    future_version = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 10,
            "effective_from": future.isoformat(),
            "condition_group": _condition("state", "CA"),
            "values": [
                {
                    "assignment_field_definition_id": field["id"],
                    "value": "4 weeks",
                }
            ],
        },
    )
    assert future_version.status_code == 201

    past_result = _query(client, [employee["id"]], today - timedelta(days=1))
    assert past_result.status_code == 200
    assert past_result.json() == [
        {
            "employee_id": employee["id"],
            "evaluation_date": (today - timedelta(days=1)).isoformat(),
            "mode": "recorded_history",
            "assignments": [],
        }
    ]

    current_result = _query(client, [employee["id"]], today)
    assert current_result.status_code == 200
    current_assignment = current_result.json()[0]["assignments"][0]
    assert current_result.json()[0]["mode"] == "current_persisted"
    assert current_assignment["value"] == "3 weeks"
    assert current_assignment["persisted_assignment_id"] is not None
    assert current_assignment["effective_from"] is not None

    before = _projection_counts(db)
    future_result = _query(client, [employee["id"]], future)
    assert future_result.status_code == 200
    projected_assignment = future_result.json()[0]["assignments"][0]
    assert future_result.json()[0]["mode"] == "calculated_future"
    assert projected_assignment["value"] == "4 weeks"
    assert projected_assignment["source_policy_version_id"] == future_version.json()["id"]
    assert projected_assignment["persisted_assignment_id"] is None
    assert projected_assignment["effective_from"] is None
    assert projected_assignment["effective_until"] is None
    assert _projection_counts(db) == before

    assert [
        item["value"]
        for item in client.get(
            f"/employees/{employee['id']}/assignments"
        ).json()
    ] == ["3 weeks"]


def test_future_resolution_does_not_depend_on_current_employee_policy_links(client, db):
    today = current_date()
    future = today + timedelta(days=30)
    field = _create_field(client)
    policy = _create_policy(
        client,
        field["id"],
        condition_value="WI",
    )
    employee = _create_employee(client, state="CA")
    assert client.get(f"/employees/{employee['id']}/assignments").json() == []
    assert db.scalars(select(EmployeePolicy)).all() == []

    future_version = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 10,
            "effective_from": future.isoformat(),
            "condition_group": _condition("state", "CA"),
            "values": [
                {
                    "assignment_field_definition_id": field["id"],
                    "value": "4 weeks",
                }
            ],
        },
    )
    assert future_version.status_code == 201

    before = _projection_counts(db)
    response = _query(client, [employee["id"]], future)
    assert response.status_code == 200
    assert [item["value"] for item in response.json()[0]["assignments"]] == [
        "4 weeks"
    ]
    assert _projection_counts(db) == before


def test_future_query_is_batch_capable_and_uses_evaluation_date_for_tenure(client):
    today = current_date()
    future = date(today.year + 2, 12, 31)
    field = _create_field(client, "senior_vacation")
    _create_policy(
        client,
        field["id"],
        condition_field="tenure",
        condition_value="2 years",
        condition_operator=">=",
        value="4 weeks",
    )
    alice = _create_employee(
        client,
        name="Alice",
        start_date=date(today.year - 1, 1, 1),
    )
    bob = _create_employee(
        client,
        name="Bob",
        start_date=date(today.year - 1, 1, 1),
    )

    response = _query(client, [bob["id"], alice["id"], bob["id"]], future)
    assert response.status_code == 200
    assert [item["employee_id"] for item in response.json()] == [
        alice["id"],
        bob["id"],
    ]
    assert all(item["mode"] == "calculated_future" for item in response.json())
    assert all(
        [assignment["value"] for assignment in item["assignments"]] == [
            "4 weeks"
        ]
        for item in response.json()
    )


def test_future_query_applies_active_overrides_without_persisting_projection(client, db):
    field = _create_field(client, "pay_schedule")
    _create_policy(client, field["id"], value="biweekly")
    employee = _create_employee(client)
    override = client.post(
        f"/employees/{employee['id']}/overrides",
        json={
            "assignment_field_definition_id": field["id"],
            "value": "monthly",
        },
    )
    assert override.status_code == 201

    before = _projection_counts(db)
    response = _query(
        client,
        [employee["id"]],
        current_date() + timedelta(days=365),
    )
    assert response.status_code == 200
    assignments = response.json()[0]["assignments"]
    assert [item["value"] for item in assignments] == ["monthly"]
    assert assignments[0]["source_override_id"] == override.json()["id"]
    assert assignments[0]["source_policy_version_id"] is None
    assert _projection_counts(db) == before


def test_assignment_query_validates_employee_ids_and_missing_employees(client):
    assert _query(client, [999_999], current_date()).status_code == 404
    assert client.post(
        "/assignment-queries",
        json={"employee_ids": [], "evaluation_date": current_date().isoformat()},
    ).status_code == 422
    assert client.post(
        "/assignment-queries",
        json={"employee_ids": [0], "evaluation_date": current_date().isoformat()},
    ).status_code == 422
