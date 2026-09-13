from sqlalchemy import inspect, select

from app.models import Employee
from app.states import STATES


def _employee(state: str) -> dict:
    return {
        "name": "Avery Chen",
        "state": state,
        "department": "Engineering",
        "employee_type": "Full-time",
    }


def test_state_catalog_contains_grouped_states_territories_and_dc(client):
    response = client.get("/employees/reference-data")

    assert response.status_code == 200
    states = response.json()["states"]
    assert states == STATES
    assert len(states) == 56
    assert len({item["code"] for item in states}) == len(states)
    assert {item["group"] for item in states} == {"states", "territories", "other"}
    assert next(item for item in states if item["code"] == "GU") == {
        "code": "GU",
        "name": "Guam",
        "label": "Guam (Territory)",
        "group": "territories",
    }
    assert next(item for item in states if item["code"] == "DC") == {
        "code": "DC",
        "name": "District of Columbia",
        "label": "District of Columbia (Federal District)",
        "group": "other",
    }


def test_employee_state_is_normalized_stored_and_displayed(client, db):
    response = client.post("/employees", json=_employee("gu"))

    assert response.status_code == 201
    assert response.json()["state"] == "GU"
    assert response.json()["state_label"] == "Guam (Territory)"
    employee = db.scalar(select(Employee).where(Employee.id == response.json()["id"]))
    assert employee is not None
    assert employee.state == "GU"
    state_column = inspect(Employee).attrs.state.columns[0]
    assert state_column.name == "state_code"


def test_employee_rejects_arbitrary_state_and_searches_by_name(client):
    assert client.post("/employees", json=_employee("Guam")).status_code == 422
    created = client.post("/employees", json=_employee("CA"))
    assert created.status_code == 201

    results = client.get("/employees", params={"search": "California"})
    assert results.status_code == 200
    assert [employee["id"] for employee in results.json()] == [created.json()["id"]]


def test_state_policy_condition_uses_the_same_codes(client):
    invalid = client.post(
        "/policies",
        json={
            "name": "Invalid state policy",
            "priority": 10,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "state", "operator": "=", "value": "Guam"}
                ],
            },
            "values": [
                {"assignment_field_definition_id": 1, "value": "enabled"}
            ],
        },
    )

    assert invalid.status_code == 422
