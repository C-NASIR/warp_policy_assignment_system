from datetime import timedelta

from app.dates import current_date


def _field(client, name: str, cardinality: str = "one") -> dict:
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": cardinality},
    )
    assert response.status_code == 201
    return response.json()


def _employee(
    client,
    name: str,
    *,
    state: str,
    department: str = "Engineering",
) -> dict:
    response = client.post(
        "/employees",
        json={
            "name": name,
            "state": state,
            "department": department,
            "employee_type": "regular",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _policy(
    client,
    field_id: int,
    *,
    name: str,
    value: str,
    state: str = "CA",
    priority: int = 10,
    effective_from=None,
    status: str = "active",
) -> dict:
    payload = {
        "name": name,
        "status": status,
        "priority": priority,
        "condition_group": {
            "logical_operator": "and",
            "conditions": [
                {"field": "state", "operator": "=", "value": state}
            ],
        },
        "values": [
            {
                "assignment_field_definition_id": field_id,
                "value": value,
            }
        ],
    }
    if effective_from is not None:
        payload["effective_from"] = effective_from.isoformat()
    response = client.post("/policies", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_assignment_summary_aggregates_sources_fields_and_employee_scope(client):
    pay = _field(client, "pay_schedule")
    access = _field(client, "application_access", "many")
    pay_policy = _policy(
        client,
        pay["id"],
        name="California weekly",
        value="weekly",
    )
    access_policy = _policy(
        client,
        access["id"],
        name="Engineering GitHub",
        value="GitHub",
        state="WI",
    )
    alice = _employee(client, "Alice", state="CA")
    _employee(client, "Bob", state="TX", department="Sales")
    group = client.post("/groups", json={"name": "Engineering"}).json()
    assert client.post(
        f"/groups/{group['id']}/employees/{alice['id']}"
    ).status_code == 201
    assert client.post(
        f"/groups/{group['id']}/policies/{access_policy['id']}"
    ).status_code == 201
    override = client.post(
        f"/employees/{alice['id']}/overrides",
        json={
            "assignment_field_definition_id": pay["id"],
            "value": "monthly",
        },
    )
    assert override.status_code == 201

    response = client.get("/assignment-summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["scope"] == "population"
    assert summary["mode"] == "current_persisted"
    assert summary["complete"] is True
    assert summary["employee_count"] == 2
    assert summary["employees_with_assignments"] == 1
    assert summary["employees_without_assignments"] == 1
    assert summary["assignment_count"] == 2
    assert summary["policy_assignment_count"] == 1
    assert summary["override_assignment_count"] == 1

    fields = {
        item["assignment_field_definition"]["name"]: item
        for item in summary["fields"]
    }
    assert fields["pay_schedule"]["value_samples"] == ["monthly"]
    assert fields["pay_schedule"]["override_assignment_count"] == 1
    assert fields["application_access"]["value_samples"] == ["GitHub"]
    assert fields["application_access"]["policy_assignment_count"] == 1

    employee_summary = client.get(
        f"/employees/{alice['id']}/assignment-summary"
    ).json()
    assert employee_summary["scope"] == "employee"
    assert employee_summary["employee_id"] == alice["id"]
    assert employee_summary["employee_count"] == 1
    assert employee_summary["assignment_count"] == 2

    pay_impact = client.get(
        f"/policies/{pay_policy['id']}/impact-summary"
    ).json()
    assert pay_impact["matched_employee_count"] == 1
    assert pay_impact["direct_match_employee_count"] == 1
    assert pay_impact["selected_employee_count"] == 0
    assert pay_impact["matched_without_selected_assignment_count"] == 1
    assert pay_impact["suppressed_by_override_employee_count"] == 1
    assert pay_impact["suppressed_by_override_assignment_count"] == 1


def test_policy_impact_distinguishes_direct_group_and_selected_reach(client):
    access = _field(client, "application_access", "many")
    policy = _policy(
        client,
        access["id"],
        name="California GitHub",
        value="GitHub",
    )
    alice = _employee(client, "Alice", state="CA")
    bob = _employee(client, "Bob", state="TX")
    group = client.post("/groups", json={"name": "Engineering"}).json()
    for employee in (alice, bob):
        assert client.post(
            f"/groups/{group['id']}/employees/{employee['id']}"
        ).status_code == 201
    assert client.post(
        f"/groups/{group['id']}/policies/{policy['id']}"
    ).status_code == 201

    impact = client.get(f"/policies/{policy['id']}/impact-summary").json()
    assert impact["effective"] is True
    assert impact["total_employee_count"] == 2
    assert impact["matched_employee_count"] == 2
    assert impact["direct_match_employee_count"] == 1
    assert impact["group_match_employee_count"] == 2
    assert impact["direct_and_group_match_employee_count"] == 1
    assert impact["selected_employee_count"] == 2
    assert impact["selected_assignment_count"] == 2
    assert impact["fields"][0]["selected_employee_count"] == 2
    assert impact["fields"][0]["configured_value_samples"] == ["GitHub"]


def test_future_summaries_report_conflicts_without_failing_the_whole_summary(client):
    pay = _field(client, "pay_schedule")
    alice = _employee(client, "Alice", state="CA")
    tomorrow = current_date() + timedelta(days=1)
    weekly = _policy(
        client,
        pay["id"],
        name="Future weekly",
        value="weekly",
        effective_from=tomorrow,
    )
    _policy(
        client,
        pay["id"],
        name="Future monthly",
        value="monthly",
        effective_from=tomorrow,
    )
    audit_count_before = int(
        client.get("/audit-logs", params={"limit": 1}).headers["X-Total-Count"]
    )

    assignment_summary = client.get(
        "/assignment-summary",
        params={"evaluation_date": tomorrow.isoformat()},
    )
    assert assignment_summary.status_code == 200
    summary = assignment_summary.json()
    assert summary["mode"] == "calculated_future"
    assert summary["complete"] is False
    assert summary["employee_count"] == 1
    assert summary["employees_with_assignments"] == 0
    assert summary["employees_without_assignments"] == 0
    assert summary["conflicted_employee_count"] == 1
    assert summary["conflicts"][0]["employee_id"] == alice["id"]
    assert summary["conflicts"][0]["assignment_field_name"] == "pay_schedule"

    impact = client.get(
        f"/policies/{weekly['id']}/impact-summary",
        params={"evaluation_date": tomorrow.isoformat()},
    ).json()
    assert impact["mode"] == "calculated_future"
    assert impact["complete"] is False
    assert impact["matched_employee_count"] == 1
    assert impact["conflicted_employee_count"] == 1
    assert impact["selected_employee_count"] == 0
    assert impact["matched_without_selected_assignment_count"] == 0
    assert client.get(f"/employees/{alice['id']}/assignments").json() == []
    audit_count_after = int(
        client.get("/audit-logs", params={"limit": 1}).headers["X-Total-Count"]
    )
    assert audit_count_after == audit_count_before


def test_ineffective_policy_summary_and_historical_boundaries_are_explicit(client):
    field = _field(client, "pay_schedule")
    archived = _policy(
        client,
        field["id"],
        name="Archived weekly",
        value="weekly",
        status="archived",
    )
    _employee(client, "Alice", state="CA")

    impact = client.get(f"/policies/{archived['id']}/impact-summary")
    assert impact.status_code == 200
    assert impact.json()["effective"] is False
    assert impact.json()["matched_employee_count"] == 0
    assert impact.json()["fields"] == []

    yesterday = current_date() - timedelta(days=1)
    assignment_history = client.get(
        "/assignment-summary",
        params={"evaluation_date": yesterday.isoformat()},
    )
    assert assignment_history.status_code == 200
    assert assignment_history.json()["mode"] == "recorded_history"

    unsupported_policy_history = client.get(
        f"/policies/{archived['id']}/impact-summary",
        params={"evaluation_date": yesterday.isoformat()},
    )
    assert unsupported_policy_history.status_code == 422
    assert unsupported_policy_history.json()["error"]["category"] == "validation"


def test_openapi_exposes_read_scoped_impact_summary_contracts(client):
    schema = client.get("/openapi.json").json()
    for path in (
        "/assignment-summary",
        "/employees/{employee_id}/assignment-summary",
        "/policies/{policy_id}/impact-summary",
    ):
        operation = schema["paths"][path]["get"]
        assert operation["x-required-scopes"] == ["read"]
        assert operation["security"] == [{"HTTPBearer": []}]
