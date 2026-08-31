from datetime import date

import pytest
from sqlalchemy import select

from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Employee,
    EmployeePolicy,
    Policy,
    PolicyVersion,
)
from app.services.policy_matching import (
    EmployeePolicyRefreshError,
    find_matching_policy_ids,
    refresh_employee_policies,
)
from app.services.condition_fields import get_condition_field_definitions


def compiled_policy(
    db,
    name: str,
    priority: int,
    clauses: list[list[tuple[str, str] | tuple[str, str, str]]],
) -> Policy:
    field_keys = {condition[0] for clause in clauses for condition in clause}
    definitions = get_condition_field_definitions(db, field_keys)
    return Policy(
        name=name,
        versions=[
            PolicyVersion(
                version_number=1,
                priority=priority,
                effective_from=date(2020, 1, 1),
                compiled_clauses=[
                    CompiledPolicyClause(
                        conditions=[
                            CompiledPolicyCondition(
                                condition_field_definition=definitions[condition[0]],
                                operator=condition[1] if len(condition) == 3 else "=",
                                value=condition[-1],
                            )
                            for condition in conditions
                        ]
                    )
                    for conditions in clauses
                ],
            )
        ],
    )


def test_finds_policy_when_any_compiled_clause_fully_matches(db):
    alice = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    matching = compiled_policy(
        db,
        "A AND (B OR C)",
        10,
        [
            [("state", "California"), ("employee_type", "regular")],
            [("state", "California"), ("department", "Engineering")],
        ],
    )
    not_matching = compiled_policy(
        db,
        "Wisconsin contractors",
        5,
        [[("state", "Wisconsin"), ("employee_type", "contractor")]],
    )
    db.add_all([alice, matching, not_matching])
    db.flush()

    assert find_matching_policy_ids(db, alice.id) == [matching.id]


def test_clause_requires_every_condition_to_match(db):
    alice = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="contractor",
    )
    policy = compiled_policy(
        db,
        "California regular",
        10,
        [[("state", "California"), ("employee_type", "regular")]],
    )
    db.add_all([alice, policy])
    db.flush()

    assert find_matching_policy_ids(db, alice.id) == []


def test_policy_is_returned_once_when_multiple_clauses_match(db):
    alice = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    policy = compiled_policy(
        db,
        "Multiple matching clauses",
        10,
        [
            [("state", "California")],
            [("department", "Engineering")],
        ],
    )
    db.add_all([alice, policy])
    db.flush()

    assert find_matching_policy_ids(db, alice.id) == [policy.id]


def test_matches_employee_columns_without_a_hard_coded_field_list(db):
    alice = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    policy = compiled_policy(db, "Named Alice", 10, [[("name", "Alice")]])
    db.add_all([alice, policy])
    db.flush()

    assert find_matching_policy_ids(db, alice.id) == [policy.id]


def test_unknown_employee_or_unsupported_condition_does_not_match(db):
    alice = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    policy = Policy(
        name="Unsupported condition",
        versions=[
            PolicyVersion(
                version_number=1,
                priority=10,
                effective_from=date(2020, 1, 1),
                compiled_clauses=[
                    CompiledPolicyClause(
                        conditions=[
                            CompiledPolicyCondition(
                                condition_field_definition=get_condition_field_definitions(
                                    db, {"state"}
                                )["state"],
                                operator="contains",
                                value="Cali",
                            )
                        ]
                    )
                ],
            )
        ],
    )
    db.add_all([alice, policy])
    db.flush()

    assert find_matching_policy_ids(db, alice.id) == []
    assert find_matching_policy_ids(db, 999_999) == []


def test_comparison_operators_use_typed_employee_facts(db):
    alice = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
        location="San Francisco",
        start_date=date(2024, 1, 15),
        manager_id=10,
    )
    policies = [
        compiled_policy(db, "Started before cutoff", 10, [[("start_date", "<", "2025-01-01")]]),
        compiled_policy(db, "Started by date", 10, [[("start_date", "<=", "2024-01-15")]]),
        compiled_policy(db, "Low manager ID", 10, [[("manager_id", "<", "100")]]),
        compiled_policy(db, "Numeric ordering", 10, [[("manager_id", "<", "2")]]),
        compiled_policy(db, "Location", 10, [[("location", "=", "San Francisco")]]),
    ]
    db.add_all([alice, *policies])
    db.flush()

    assert find_matching_policy_ids(db, alice.id) == [
        policies[0].id,
        policies[1].id,
        policies[2].id,
        policies[4].id,
    ]


def test_false_date_comparison_does_not_match(db):
    alice = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
        start_date=date(2026, 1, 1),
    )
    policy = compiled_policy(db, "Has early start", 10, [[("start_date", "<", "2025-01-01")]])
    db.add_all([alice, policy])
    db.flush()

    assert find_matching_policy_ids(db, alice.id) == []


def test_refresh_employee_policies_replaces_stale_links(db):
    alice = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    california = compiled_policy(
        db,
        "California policy",
        10,
        [[("state", "California")]],
    )
    wisconsin = compiled_policy(
        db,
        "Wisconsin policy",
        10,
        [[("state", "Wisconsin")]],
    )
    db.add_all([alice, california, wisconsin])
    db.flush()
    assert alice.policies == []

    links = refresh_employee_policies(db, alice.id)

    assert [(link.employee_id, link.policy_id) for link in links] == [(alice.id, california.id)]
    assert [policy.id for policy in alice.policies] == [california.id]

    alice.state = "Wisconsin"
    db.flush()
    replacement = refresh_employee_policies(db, alice.id)

    assert [(link.employee_id, link.policy_id) for link in replacement] == [(alice.id, wisconsin.id)]
    assert [policy.id for policy in alice.policies] == [wisconsin.id]
    assert db.scalars(select(EmployeePolicy)).all() == replacement


def test_refresh_employee_policies_rejects_unknown_employee(db):
    with pytest.raises(EmployeePolicyRefreshError, match="Employee 999 not found"):
        refresh_employee_policies(db, 999)
