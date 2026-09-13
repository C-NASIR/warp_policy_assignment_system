from datetime import UTC, datetime, timedelta

from app.services import change_approvals

APPROVAL_SECRET = "0123456789abcdef0123456789abcdef"


def _field(client):
    response = client.post(
        "/assignment-fields",
        json={"name": "pay_schedule", "cardinality": "one"},
    )
    assert response.status_code == 201
    return response.json()


def _policy(client, field_id, *, name, state, value):
    response = client.post(
        "/policies",
        json={
            "name": name,
            "priority": 10,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [{"field": "state", "operator": "=", "value": state}],
            },
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


def _employee_change(name="Alice", state="CA"):
    return {
        "type": "employee_create",
        "employee": {
            "name": name,
            "state": state,
            "department": "Engineering",
            "employee_type": "regular",
        },
    }


def _policy_create_change(field_id):
    return {
        "type": "policy_create",
        "policy": {
            "name": "California payroll",
            "status": "active",
            "priority": 20,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "state", "operator": "=", "value": "CA"}
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": field_id,
                    "value": "biweekly",
                }
            ],
        },
    }


def _approved_preview(client, change):
    response = client.post("/change-previews", json=change)
    assert response.status_code == 200
    preview = response.json()
    assert preview["valid"] is True
    assert preview["approval"] is not None
    return preview


def test_approved_change_executes_once_and_replays_result(client, monkeypatch):
    monkeypatch.setenv("CHANGE_APPROVAL_SECRET", APPROVAL_SECRET)
    now = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(change_approvals, "current_datetime", lambda: now)
    field = _field(client)
    _policy(
        client,
        field["id"],
        name="California weekly",
        state="CA",
        value="weekly",
    )
    change = _employee_change()
    preview = _approved_preview(client, change)
    body = {
        "approval_token": preview["approval"]["token"],
        "change": change,
    }

    execution = client.post("/change-executions", json=body)

    assert execution.status_code == 200, execution.text
    result = execution.json()
    assert result["status"] == "executed"
    assert result["replayed"] is False
    assert result["executed_by"] == "api"
    assert result["resources"]["employee_id"] == result["changes"][0]["employee_id"]
    assert [item["value"] for item in result["changes"][0]["added"]] == ["weekly"]

    monkeypatch.setattr(
        change_approvals,
        "current_datetime",
        lambda: now + timedelta(seconds=901),
    )
    replay = client.post("/change-executions", json=body)
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["approval_id"] == result["approval_id"]
    assert replay.json()["resources"] == result["resources"]
    assert len(client.get("/employees").json()) == 1


def test_approved_policy_create_executes_the_previewed_change(client, monkeypatch):
    monkeypatch.setenv("CHANGE_APPROVAL_SECRET", APPROVAL_SECRET)
    field = _field(client)
    employee = client.post(
        "/employees",
        json=_employee_change()["employee"],
    ).json()
    change = _policy_create_change(field["id"])
    preview = _approved_preview(client, change)

    execution = client.post(
        "/change-executions",
        json={
            "approval_token": preview["approval"]["token"],
            "change": change,
        },
    )

    assert execution.status_code == 200, execution.text
    result = execution.json()
    assert result["resources"]["policy_id"] > 0
    assert result["resources"]["policy_version_id"] > 0
    assert result["affected_employee_count"] == 1
    assert result["changes"][0]["employee_id"] == employee["id"]
    assert (
        client.get(f"/policies/{result['resources']['policy_id']}").status_code == 200
    )
    assignments = client.get(f"/employees/{employee['id']}/assignments").json()
    assert [assignment["value"] for assignment in assignments] == ["biweekly"]


def test_unexecuted_approval_expires(client, monkeypatch):
    monkeypatch.setenv("CHANGE_APPROVAL_SECRET", APPROVAL_SECRET)
    now = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(change_approvals, "current_datetime", lambda: now)
    change = _employee_change()
    preview = _approved_preview(client, change)
    monkeypatch.setattr(
        change_approvals,
        "current_datetime",
        lambda: now + timedelta(seconds=901),
    )

    response = client.post(
        "/change-executions",
        json={
            "approval_token": preview["approval"]["token"],
            "change": change,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "change_approval_expired"
    assert client.get("/employees").json() == []


def test_execution_rejects_changed_input_and_invalid_signature(client, monkeypatch):
    monkeypatch.setenv("CHANGE_APPROVAL_SECRET", APPROVAL_SECRET)
    change = _employee_change()
    preview = _approved_preview(client, change)
    changed = _employee_change(name="Mallory")

    mismatch = client.post(
        "/change-executions",
        json={
            "approval_token": preview["approval"]["token"],
            "change": changed,
        },
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "change_approval_change_mismatch"

    invalid = client.post(
        "/change-executions",
        json={
            "approval_token": preview["approval"]["token"] + "tampered",
            "change": change,
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "change_approval_token_invalid"
    assert client.get("/employees").json() == []


def test_execution_rolls_back_when_approved_impact_is_stale(client, monkeypatch):
    monkeypatch.setenv("CHANGE_APPROVAL_SECRET", APPROVAL_SECRET)
    field = _field(client)
    change = _employee_change(name="Bob", state="TX")
    preview = _approved_preview(client, change)
    assert preview["before_assignments"] == []
    assert preview["after_assignments"] == []
    _policy(
        client,
        field["id"],
        name="Texas monthly",
        state="TX",
        value="monthly",
    )

    response = client.post(
        "/change-executions",
        json={
            "approval_token": preview["approval"]["token"],
            "change": change,
        },
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "change_approval_stale"
    current_preview = error["issues"][0]["metadata"]["current_preview"]
    assert current_preview["type"] == "employee_create"
    assert current_preview["before_assignments"] == []
    assert [item["value"] for item in current_preview["after_assignments"]] == [
        "monthly"
    ]
    assert client.get("/employees").json() == []


def test_execution_rejects_a_concurrent_target_edit(client, monkeypatch):
    monkeypatch.setenv("CHANGE_APPROVAL_SECRET", APPROVAL_SECRET)
    employee = client.post("/employees", json=_employee_change()["employee"]).json()
    change = {
        "type": "employee_update",
        "employee_id": employee["id"],
        "changes": {"state": "TX"},
    }
    preview = _approved_preview(client, change)
    concurrent = client.patch(
        f"/employees/{employee['id']}",
        json={"department": "Sales"},
    )
    assert concurrent.status_code == 200

    response = client.post(
        "/change-executions",
        json={
            "approval_token": preview["approval"]["token"],
            "change": change,
        },
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "change_approval_stale"
    assert error["issues"][0]["metadata"]["stage"] == "target_precondition"
    current = client.get(f"/employees/{employee['id']}").json()
    assert current["state"] == "CA"
    assert current["department"] == "Sales"


def test_preview_explains_when_approved_execution_is_not_configured(
    client,
    monkeypatch,
):
    monkeypatch.delenv("CHANGE_APPROVAL_SECRET", raising=False)
    change = _employee_change()
    preview = client.post("/change-previews", json=change).json()

    assert preview["approval"] is None
    assert preview["warnings"] == [
        (
            "Approved execution is unavailable because CHANGE_APPROVAL_SECRET is not "
            "configured"
        )
    ]
    response = client.post(
        "/change-executions",
        json={"approval_token": "unconfigured", "change": change},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "change_approval_not_configured"
