from datetime import date, timedelta

import pytest

from app.dates import current_date
from app.models import (
    AssignmentFieldDefinition,
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Employee,
    EmployeeGroupMembership,
    EmployeePolicy,
    Group,
    GroupPolicy,
    Policy,
    PolicyFieldValue,
    PolicyVersion,
)
from app.services.condition_fields import get_condition_field_definitions
from app.services.policy_engine import resolve_employee_assignments
from app.services.policy_matching import (
    find_matching_policy_ids,
    refresh_employee_policies,
)
from app.services.policy_versions import (
    EffectivePolicyVersionConflictError,
    get_effective_policy_version,
)
from app.services.reconciliation import refresh_employee_assignments


def condition_group(state="California"):
    return {
        "logical_operator": "and",
        "conditions": [{"field": "state", "operator": "=", "value": state}],
    }


def serialized_condition_group(state="California"):
    return {
        **condition_group(state),
        "child_groups": [],
    }


def compiled_state_clause(db, state="California"):
    state_definition = get_condition_field_definitions(db, {"state"})["state"]
    return [
        CompiledPolicyClause(
            conditions=[
                CompiledPolicyCondition(
                    condition_field_definition=state_definition,
                    operator="=",
                    value=state,
                )
            ]
        )
    ]


def test_policy_api_creates_version_one_and_schedules_later_versions(client):
    field = client.post(
        "/assignment-fields",
        json={"name": "vacation", "cardinality": "one"},
    ).json()
    today = current_date()
    response = client.post(
        "/policies",
        json={
            "name": "California Vacation",
            "priority": 10,
            "effective_from": today.isoformat(),
            "created_by": "policy-team",
            "condition_group": condition_group(),
            "values": [
                {"assignment_field_definition_id": field["id"], "value": "2 weeks"}
            ],
        },
    )
    assert response.status_code == 201
    policy = response.json()
    assert policy["status"] == "active"
    assert policy["versions"][0]["version_number"] == 1
    assert policy["versions"][0]["created_by"] == "policy-team"
    assert policy["versions"][0]["condition_group"] == (
        serialized_condition_group()
    )
    assert client.get(f"/policies/{policy['id']}").json()["versions"][0][
        "condition_group"
    ] == serialized_condition_group()
    assert client.get("/policies").json()[0]["versions"][0][
        "condition_group"
    ] == serialized_condition_group()

    next_start = today + timedelta(days=365)
    second = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 20,
            "effective_from": next_start.isoformat(),
            "condition_group": condition_group(),
            "values": [
                {"assignment_field_definition_id": field["id"], "value": "3 weeks"}
            ],
        },
    )
    assert second.status_code == 201
    assert second.json()["version_number"] == 2
    assert second.json()["condition_group"] == serialized_condition_group()

    versions = client.get(f"/policies/{policy['id']}/versions").json()
    assert [version["version_number"] for version in versions] == [1, 2]
    assert versions[0]["effective_until"] == (
        next_start - timedelta(days=1)
    ).isoformat()
    assert versions[1]["effective_until"] is None
    assert client.get(
        f"/policies/{policy['id']}/versions/{versions[1]['id']}"
    ).json() == versions[1]

    overlap = client.post(
        f"/policies/{policy['id']}/versions",
        json={
            "priority": 30,
            "effective_from": (today + timedelta(days=1)).isoformat(),
            "condition_group": condition_group(),
        },
    )
    assert overlap.status_code == 409


def test_policy_version_reads_return_the_complete_nested_condition_tree(client):
    field = client.post(
        "/assignment-fields",
        json={"name": "application_access", "cardinality": "many"},
    ).json()
    condition_tree = {
        "logical_operator": "and",
        "conditions": [
            {"field": "employee_type", "operator": "=", "value": "regular"}
        ],
        "child_groups": [
            {
                "logical_operator": "or",
                "conditions": [
                    {
                        "field": "state",
                        "operator": "=",
                        "value": "California",
                    },
                    {
                        "field": "department",
                        "operator": "=",
                        "value": "Engineering",
                    },
                ],
                "child_groups": [],
            }
        ],
    }
    response = client.post(
        "/policies",
        json={
            "name": "Engineering access",
            "priority": 20,
            "condition_group": condition_tree,
            "values": [
                {
                    "assignment_field_definition_id": field["id"],
                    "value": "GitHub",
                }
            ],
        },
    )
    assert response.status_code == 201
    policy = response.json()
    version = policy["versions"][0]
    assert version["condition_group"] == condition_tree

    assert client.get(
        f"/policies/{policy['id']}/versions/{version['id']}"
    ).json()["condition_group"] == condition_tree
    assert client.get(f"/policies/{policy['id']}/versions").json()[0][
        "condition_group"
    ] == condition_tree


def test_effective_version_selection_handles_boundaries_gaps_and_archiving(db):
    policy = Policy(
        name="Vacation",
        versions=[
            PolicyVersion(
                version_number=1,
                priority=10,
                effective_from=date(2025, 1, 1),
                effective_until=date(2025, 6, 30),
            ),
            PolicyVersion(
                version_number=2,
                priority=20,
                effective_from=date(2026, 1, 1),
            ),
        ],
    )
    db.add(policy)
    db.flush()

    first_boundary = get_effective_policy_version(db, policy.id, date(2025, 1, 1))
    last_boundary = get_effective_policy_version(db, policy.id, date(2025, 6, 30))
    later_version = get_effective_policy_version(db, policy.id, date(2027, 1, 1))

    assert first_boundary is not None
    assert first_boundary.version_number == 1
    assert last_boundary is not None
    assert last_boundary.version_number == 1
    assert get_effective_policy_version(db, policy.id, date(2025, 8, 1)) is None
    assert later_version is not None
    assert later_version.version_number == 2

    policy.status = "archived"
    db.flush()
    assert get_effective_policy_version(db, policy.id, date(2026, 1, 1)) is None


def test_effective_version_selection_rejects_corrupt_overlapping_data(db):
    policy = Policy(
        name="Overlapping",
        versions=[
            PolicyVersion(
                version_number=1,
                priority=10,
                effective_from=date(2025, 1, 1),
                effective_until=date(2025, 12, 31),
            ),
            PolicyVersion(
                version_number=2,
                priority=20,
                effective_from=date(2025, 6, 1),
            ),
        ],
    )
    db.add(policy)
    db.flush()

    with pytest.raises(
        EffectivePolicyVersionConflictError,
        match="multiple versions effective",
    ):
        get_effective_policy_version(db, policy.id, date(2025, 7, 1))


def test_group_policy_uses_version_for_evaluation_date_and_assignment_source(db):
    employee = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    field = AssignmentFieldDefinition(name="vacation", cardinality="one")
    policy = Policy(
        name="Engineering Vacation",
        versions=[
            PolicyVersion(
                version_number=1,
                priority=10,
                effective_from=date(2025, 1, 1),
                effective_until=date(2025, 12, 31),
                compiled_clauses=compiled_state_clause(db, "Wisconsin"),
                values=[PolicyFieldValue(assignment_field_definition=field, value="2 weeks")],
            ),
            PolicyVersion(
                version_number=2,
                priority=20,
                effective_from=date(2026, 1, 1),
                compiled_clauses=compiled_state_clause(db, "Wisconsin"),
                values=[PolicyFieldValue(assignment_field_definition=field, value="3 weeks")],
            ),
        ],
    )
    group = Group(name="Engineering")
    db.add_all([employee, policy, group])
    db.flush()
    db.add_all(
        [
            EmployeeGroupMembership(employee_id=employee.id, group_id=group.id),
            GroupPolicy(group_id=group.id, policy_id=policy.id),
        ]
    )
    db.flush()

    refresh_employee_policies(db, employee.id, date(2025, 6, 1))
    first = refresh_employee_assignments(db, employee, date(2025, 6, 1))
    assert [(item.value, item.source_policy_version_id) for item in first] == [
        ("2 weeks", policy.versions[0].id)
    ]

    refresh_employee_policies(db, employee.id, date(2026, 6, 1))
    second = refresh_employee_assignments(db, employee, date(2026, 6, 1))
    assert [(item.value, item.source_policy_version_id) for item in second] == [
        ("3 weeks", policy.versions[1].id)
    ]
    assert db.get(EmployeePolicy, (employee.id, policy.id)) is not None


def test_direct_matching_uses_only_the_effective_versions_conditions(db):
    employee = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    policy = Policy(
        name="State policy",
        versions=[
            PolicyVersion(
                version_number=1,
                priority=10,
                effective_from=date(2025, 1, 1),
                effective_until=date(2025, 12, 31),
                compiled_clauses=compiled_state_clause(db, "California"),
            ),
            PolicyVersion(
                version_number=2,
                priority=10,
                effective_from=date(2026, 1, 1),
                compiled_clauses=compiled_state_clause(db, "Wisconsin"),
            ),
        ],
    )
    db.add_all([employee, policy])
    db.flush()

    assert find_matching_policy_ids(db, employee.id, date(2025, 6, 1)) == [
        policy.id
    ]
    assert find_matching_policy_ids(db, employee.id, date(2026, 6, 1)) == []


def test_version_priority_changes_the_winner_across_evaluation_dates(db):
    employee = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    field = AssignmentFieldDefinition(name="pay_schedule", cardinality="one")
    changing = Policy(
        name="Changing priority",
        versions=[
            PolicyVersion(
                version_number=1,
                priority=5,
                effective_from=date(2025, 1, 1),
                effective_until=date(2025, 12, 31),
                values=[PolicyFieldValue(assignment_field_definition=field, value="weekly")],
            ),
            PolicyVersion(
                version_number=2,
                priority=20,
                effective_from=date(2026, 1, 1),
                values=[PolicyFieldValue(assignment_field_definition=field, value="weekly")],
            ),
        ],
    )
    steady = Policy(
        name="Steady priority",
        versions=[
            PolicyVersion(
                version_number=1,
                priority=10,
                effective_from=date(2025, 1, 1),
                effective_until=date(2025, 12, 31),
                values=[PolicyFieldValue(assignment_field_definition=field, value="monthly")],
            ),
            PolicyVersion(
                version_number=2,
                priority=10,
                effective_from=date(2026, 1, 1),
                values=[PolicyFieldValue(assignment_field_definition=field, value="monthly")],
            ),
        ],
    )
    db.add_all([employee, changing, steady])
    db.flush()
    employee.policies = [changing, steady]
    db.flush()

    old_result = resolve_employee_assignments(db, employee, date(2025, 6, 1))
    new_result = resolve_employee_assignments(db, employee, date(2026, 6, 1))

    assert [(item.value, item.source_policy_version_id) for item in old_result] == [
        ("monthly", steady.versions[0].id)
    ]
    assert [(item.value, item.source_policy_version_id) for item in new_result] == [
        ("weekly", changing.versions[1].id)
    ]
