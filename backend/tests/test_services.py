from datetime import date

import pytest

from app.models import (
    AssignmentFieldDefinition,
    Employee,
    Policy,
    PolicyFieldValue,
    PolicyVersion,
)
from app.services.policy_engine import PolicyConflictError, resolve_employee_assignments


def versioned_policy(name, priority, values):
    version = PolicyVersion(
        version_number=1,
        priority=priority,
        effective_from=date(2020, 1, 1),
        values=values,
    )
    return Policy(name=name, versions=[version])


def test_policy_engine_is_independently_callable(db):
    employee = Employee(name="Alice", state="California", department="Engineering", employee_type="regular")
    pay = AssignmentFieldDefinition(name="pay_schedule", cardinality="one")
    access = AssignmentFieldDefinition(name="application_access", cardinality="many")
    db.add_all([employee, pay, access])
    db.flush()
    low = versioned_policy(
        "Low",
        5,
        [
            PolicyFieldValue(assignment_field_definition=pay, value="weekly"),
            PolicyFieldValue(assignment_field_definition=access, value="GitHub"),
        ],
    )
    high = versioned_policy(
        "High",
        20,
        [
            PolicyFieldValue(assignment_field_definition=pay, value="biweekly"),
            PolicyFieldValue(assignment_field_definition=access, value="Slack"),
        ],
    )
    db.add_all([low, high])
    db.flush()

    employee.policies = [low, high]
    db.flush()
    result = resolve_employee_assignments(db, employee)
    assert {(item.value, item.source_policy_version_id) for item in result} == {
        ("biweekly", high.versions[0].id),
        ("GitHub", low.versions[0].id),
        ("Slack", high.versions[0].id),
    }


def test_same_priority_same_value_is_not_a_conflict(db):
    employee = Employee(name="A", state="CA", department="Eng", employee_type="regular")
    field = AssignmentFieldDefinition(name="schedule", cardinality="one")
    first = versioned_policy(
        "First",
        10,
        [PolicyFieldValue(assignment_field_definition=field, value="weekly")],
    )
    second = versioned_policy(
        "Second",
        10,
        [PolicyFieldValue(assignment_field_definition=field, value="weekly")],
    )
    db.add_all([employee, field, first, second])
    db.flush()
    employee.policies = [first, second]
    db.flush()
    result = resolve_employee_assignments(db, employee)
    assert len(result) == 1
    assert result[0].value == "weekly"
    assert result[0].source_policy_version_id == first.versions[0].id


def test_service_raises_for_equal_priority_different_values(db):
    employee = Employee(name="A", state="CA", department="Eng", employee_type="regular")
    field = AssignmentFieldDefinition(name="schedule", cardinality="one")
    first = versioned_policy(
        "First",
        10,
        [PolicyFieldValue(assignment_field_definition=field, value="weekly")],
    )
    second = versioned_policy(
        "Second",
        10,
        [PolicyFieldValue(assignment_field_definition=field, value="monthly")],
    )
    db.add_all([employee, field, first, second])
    db.flush()
    employee.policies = [first, second]
    db.flush()
    with pytest.raises(PolicyConflictError, match="Conflicting values"):
        resolve_employee_assignments(db, employee)
