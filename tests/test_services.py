import pytest

from app.models import Employee, FieldDefinition, Policy, PolicyFieldValue
from app.services.policy_engine import PolicyConflictError, resolve_employee_assignments


def test_policy_engine_is_independently_callable(db):
    employee = Employee(name="Alice", state="California", department="Engineering", employee_type="regular")
    pay = FieldDefinition(name="pay_schedule", cardinality="one")
    access = FieldDefinition(name="application_access", cardinality="many")
    db.add_all([employee, pay, access])
    db.flush()
    low = Policy(name="Low", priority=5)
    high = Policy(name="High", priority=20)
    low.values = [PolicyFieldValue(field_definition=pay, value="weekly"), PolicyFieldValue(field_definition=access, value="GitHub")]
    high.values = [PolicyFieldValue(field_definition=pay, value="biweekly"), PolicyFieldValue(field_definition=access, value="Slack")]
    db.add_all([low, high])
    db.flush()

    employee.policies = [low, high]
    db.flush()
    result = resolve_employee_assignments(db, employee)
    assert {(item.value, item.source_policy_id) for item in result} == {
        ("biweekly", high.id),
        ("GitHub", low.id),
        ("Slack", high.id),
    }


def test_same_priority_same_value_is_not_a_conflict(db):
    employee = Employee(name="A", state="CA", department="Eng", employee_type="regular")
    field = FieldDefinition(name="schedule", cardinality="one")
    first = Policy(name="First", priority=10)
    second = Policy(name="Second", priority=10)
    first.values = [PolicyFieldValue(field_definition=field, value="weekly")]
    second.values = [PolicyFieldValue(field_definition=field, value="weekly")]
    db.add_all([employee, field, first, second])
    db.flush()
    employee.policies = [first, second]
    db.flush()
    result = resolve_employee_assignments(db, employee)
    assert len(result) == 1
    assert result[0].value == "weekly"
    assert result[0].source_policy_id == first.id


def test_service_raises_for_equal_priority_different_values(db):
    employee = Employee(name="A", state="CA", department="Eng", employee_type="regular")
    field = FieldDefinition(name="schedule", cardinality="one")
    first = Policy(name="First", priority=10)
    second = Policy(name="Second", priority=10)
    first.values = [PolicyFieldValue(field_definition=field, value="weekly")]
    second.values = [PolicyFieldValue(field_definition=field, value="monthly")]
    db.add_all([employee, field, first, second])
    db.flush()
    employee.policies = [first, second]
    db.flush()
    with pytest.raises(PolicyConflictError, match="Conflicting values"):
        resolve_employee_assignments(db, employee)
