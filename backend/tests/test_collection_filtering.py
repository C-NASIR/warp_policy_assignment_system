from datetime import timedelta

from app.dates import current_date, current_datetime


def _employee(
    client,
    name: str,
    *,
    state: str,
    department: str,
    employee_type: str = "regular",
    manager_id: int | None = None,
) -> dict:
    payload = {
        "name": name,
        "state": state,
        "department": department,
        "employee_type": employee_type,
    }
    if manager_id is not None:
        payload["manager_id"] = manager_id
    response = client.post("/employees", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _assert_page(
    response,
    *,
    total: int,
    limit: int,
    offset: int,
) -> list[dict]:
    assert response.status_code == 200, response.text
    assert response.headers["X-Total-Count"] == str(total)
    assert response.headers["X-Limit"] == str(limit)
    assert response.headers["X-Offset"] == str(offset)
    return response.json()


def _assignment_field(client, name: str = "pay_schedule") -> dict:
    response = client.post(
        "/assignment-fields",
        json={"name": name, "cardinality": "one"},
    )
    assert response.status_code == 201
    return response.json()


def _policy(client, field_id: int, name: str, *, status: str = "active") -> dict:
    response = client.post(
        "/policies",
        json={
            "name": name,
            "status": status,
            "priority": 10,
            "condition_group": {
                "logical_operator": "and",
                "conditions": [
                    {"field": "state", "operator": "=", "value": "CA"}
                ],
            },
            "values": [
                {
                    "assignment_field_definition_id": field_id,
                    "value": "weekly",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_employee_filters_compose_with_pagination_and_total_count(client):
    manager = _employee(
        client,
        "Manager",
        state="WI",
        department="Engineering",
    )
    _employee(
        client,
        "Alice",
        state="CA",
        department="Engineering",
        manager_id=manager["id"],
    )
    _employee(
        client,
        "Bob",
        state="TX",
        department="Sales",
    )
    _employee(
        client,
        "Carol",
        state="CA",
        department="Engineering",
        manager_id=manager["id"],
    )

    page = _assert_page(
        client.get(
            "/employees",
            params={
                "state": "CA",
                "department": "Engineering",
                "has_manager": True,
                "limit": 1,
                "offset": 1,
            },
        ),
        total=2,
        limit=1,
        offset=1,
    )
    assert [employee["name"] for employee in page] == ["Carol"]


def test_employee_search_accepts_padded_employee_id(client):
    employee = _employee(
        client,
        "Alex Morgan",
        state="IL",
        department="Operations",
    )
    _employee(
        client,
        "Someone Else",
        state="TX",
        department="Sales",
    )

    response = client.get("/employees", params={"search": f"#{employee['id']:04d}"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [employee["id"]]


def test_manager_candidates_are_bounded_minimal_and_cycle_safe(client):
    manager = _employee(
        client,
        "Alex Morgan",
        state="IL",
        department="Engineering",
    )
    report = _employee(
        client,
        "Alex Morgan",
        state="IL",
        department="Support",
        manager_id=manager["id"],
    )
    grandchild = _employee(
        client,
        "Taylor Reed",
        state="IL",
        department="Support",
        manager_id=report["id"],
    )

    by_id = client.get(
        "/employees/manager-candidates",
        params={"search": f"#{manager['id']:04d}", "limit": 1},
    )
    assert by_id.status_code == 200
    assert by_id.json() == [
        {
            "id": manager["id"],
            "label": f"Alex Morgan · Engineering · #{manager['id']:04d}",
        }
    ]

    editing_manager = client.get(
        "/employees/manager-candidates",
        params={"employee_id": manager["id"]},
    )
    assert editing_manager.status_code == 200
    assert {
        item["id"] for item in editing_manager.json()
    }.isdisjoint({manager["id"], report["id"], grandchild["id"]})


def test_employee_reference_data_returns_distinct_sorted_values(client):
    _employee(
        client,
        "Alice",
        state="CA",
        department="Engineering",
        employee_type="Full-time",
    )
    _employee(
        client,
        "Bob",
        state="TX",
        department="Sales",
        employee_type="Contractor",
    )
    _employee(
        client,
        "Carol",
        state="WI",
        department="Engineering",
        employee_type="Full-time",
    )

    response = client.get("/employees/reference-data")

    assert response.status_code == 200
    assert response.json()["departments"] == ["Engineering", "Sales"]
    assert response.json()["employee_types"] == ["Contractor", "Full-time"]

    search = _assert_page(
        client.get("/employees", params={"search": "alice"}),
        total=1,
        limit=100,
        offset=0,
    )
    assert search[0]["name"] == "Alice"

    invalid = client.get("/employees", params={"limit": 0})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["category"] == "validation"


def test_policy_group_and_metadata_collections_filter_and_page(client):
    field = _assignment_field(client)
    active = _policy(client, field["id"], "California weekly")
    _policy(client, field["id"], "Old California weekly", status="archived")
    alice = _employee(
        client,
        "Alice",
        state="CA",
        department="Engineering",
    )
    group = client.post("/groups", json={"name": "Engineering"}).json()
    assert client.post(
        f"/groups/{group['id']}/employees/{alice['id']}"
    ).status_code == 201
    assert client.post(
        f"/groups/{group['id']}/policies/{active['id']}"
    ).status_code == 201

    groups = _assert_page(
        client.get("/groups", params={"search": "engineer"}),
        total=1,
        limit=100,
        offset=0,
    )
    assert groups[0]["member_count"] == 1
    assert groups[0]["policy_count"] == 1

    policies = _assert_page(
        client.get("/policies", params={"status": "archived", "search": "old"}),
        total=1,
        limit=100,
        offset=0,
    )
    assert policies[0]["name"] == "Old California weekly"

    versions = _assert_page(
        client.get(
            f"/policies/{active['id']}/versions",
            params={"effective_on": current_date().isoformat()},
        ),
        total=1,
        limit=100,
        offset=0,
    )
    assert versions[0]["policy_id"] == active["id"]

    members = _assert_page(
        client.get(
            f"/groups/{group['id']}/employees",
            params={"department": "Engineering"},
        ),
        total=1,
        limit=100,
        offset=0,
    )
    assert members[0]["id"] == alice["id"]

    group_policies = _assert_page(
        client.get(
            f"/groups/{group['id']}/policies",
            params={"status": "active"},
        ),
        total=1,
        limit=100,
        offset=0,
    )
    assert group_policies[0]["id"] == active["id"]

    assignment_fields = _assert_page(
        client.get("/assignment-fields", params={"cardinality": "one"}),
        total=1,
        limit=100,
        offset=0,
    )
    assert assignment_fields[0]["name"] == "pay_schedule"

    derived_fields = client.get(
        "/condition-fields",
        params={"field_type": "derived", "limit": 2},
    )
    assert derived_fields.status_code == 200
    assert int(derived_fields.headers["X-Total-Count"]) >= 2
    assert len(derived_fields.json()) == 2


def test_assignment_override_and_audit_collections_support_filters(client):
    field = _assignment_field(client)
    _policy(client, field["id"], "California weekly")
    alice = _employee(
        client,
        "Alice",
        state="CA",
        department="Engineering",
    )
    override = client.post(
        f"/employees/{alice['id']}/overrides",
        json={
            "assignment_field_definition_id": field["id"],
            "value": "monthly",
        },
    )
    assert override.status_code == 201

    assignments = _assert_page(
        client.get(
            f"/employees/{alice['id']}/assignments",
            params={"source": "override", "value": "monthly"},
        ),
        total=1,
        limit=100,
        offset=0,
    )
    assert assignments[0]["source_override_id"] == override.json()["id"]

    overrides = _assert_page(
        client.get(
            f"/employees/{alice['id']}/overrides",
            params={"assignment_field_definition_id": field["id"]},
        ),
        total=1,
        limit=100,
        offset=0,
    )
    assert overrides[0]["value"] == "monthly"

    history = client.get(
        f"/employees/{alice['id']}/assignments/history",
        params={
            "status": "all",
            "effective_to": (current_datetime() + timedelta(days=1)).isoformat(),
            "limit": 1,
        },
    )
    assert history.status_code == 200
    assert int(history.headers["X-Total-Count"]) >= 2
    assert len(history.json()) == 1
    assert set(history.json()[0]) == {
        "id",
        "value",
        "source_type",
        "effective_from",
        "effective_until",
        "assignment_field_definition",
    }
    assert set(history.json()[0]["assignment_field_definition"]) == {"id", "name"}

    audits = client.get(
        "/audit-logs",
        params={"search": "employee", "limit": 1},
    )
    assert audits.status_code == 200
    assert int(audits.headers["X-Total-Count"]) >= 1
    assert len(audits.json()) == 1

    facets = client.get("/audit-logs/facets")
    assert facets.status_code == 200
    assert {"Employee", "EmployeeOverride", "Policy"} <= set(
        facets.json()["entity_types"]
    )
    assert "created" in facets.json()["actions"]

    override_audits = client.get(
        "/audit-logs",
        params={"entity_type": "EmployeeOverride", "sort": "desc"},
    ).json()
    assert override_audits[0]["entity_label"] == "Alice · Manual override"


def test_credentials_and_scope_catalog_filter_without_exposing_secrets(client):
    first = client.post(
        "/auth/credentials",
        json={
            "name": "mcp-reader",
            "subject": "mcp-agent",
            "scopes": ["read", "preview"],
        },
    ).json()
    second = client.post(
        "/auth/credentials",
        json={
            "name": "frontend-reader",
            "subject": "frontend-gateway",
            "scopes": ["read"],
        },
    ).json()
    assert client.delete(f"/auth/credentials/{second['id']}").status_code == 204

    credentials = _assert_page(
        client.get(
            "/auth/credentials",
            params={"subject": "mcp-agent", "scope": "preview"},
        ),
        total=1,
        limit=100,
        offset=0,
    )
    assert credentials[0]["id"] == first["id"]
    assert "token" not in credentials[0]
    assert "token_hash" not in credentials[0]

    revoked = _assert_page(
        client.get("/auth/credentials", params={"status": "revoked"}),
        total=1,
        limit=100,
        offset=0,
    )
    assert revoked[0]["id"] == second["id"]

    scopes = client.get(
        "/auth/scopes",
        params={"search": "change", "limit": 1},
    )
    assert scopes.status_code == 200
    assert int(scopes.headers["X-Total-Count"]) >= 1
    assert len(scopes.json()) == 1


def test_openapi_documents_collection_pagination_contract(client):
    schema = client.get("/openapi.json").json()
    employees = schema["paths"]["/employees"]["get"]
    query_parameters = {
        parameter["name"] for parameter in employees["parameters"]
    }
    assert {"limit", "offset", "search", "state", "department"} <= query_parameters
    assert set(employees["responses"]["200"]["headers"]) == {
        "X-Total-Count",
        "X-Limit",
        "X-Offset",
    }

    single_employee = schema["paths"]["/employees/{employee_id}"]["get"]
    assert "headers" not in single_employee["responses"]["200"]

    assignment_query = schema["paths"]["/assignment-queries"]["post"]
    assert "headers" not in assignment_query["responses"]["200"]
