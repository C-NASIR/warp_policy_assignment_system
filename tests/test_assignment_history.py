from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.dates import ensure_utc
from app.models import (
    Employee,
    EmployeeAssignment,
    FieldDefinition,
    Policy,
    PolicyFieldValue,
    PolicyVersion,
)
from app.services.employee_assignments import (
    get_employee_assignment_history,
    get_employee_assignments_as_of,
)
from app.services.reconciliation import (
    AssignmentReconciliationOrderError,
    refresh_employee_assignments,
)


def make_policy(name, field, value, priority=10):
    return Policy(
        name=name,
        versions=[
            PolicyVersion(
                version_number=1,
                priority=priority,
                effective_from=date(2020, 1, 1),
                values=[PolicyFieldValue(field_definition=field, value=value)],
            )
        ],
    )


def make_employee():
    return Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )


def test_reconciliation_preserves_unchanged_rows_and_tracks_changes(db):
    employee = make_employee()
    field = FieldDefinition(name="pay_schedule", cardinality="one")
    policy = make_policy("Schedule", field, "weekly")
    employee.policies = [policy]
    db.add(employee)
    db.flush()

    first_at = datetime(2025, 1, 1, 9, tzinfo=UTC)
    unchanged_at = datetime(2025, 2, 1, 9, tzinfo=UTC)
    changed_at = datetime(2025, 3, 1, 9, tzinfo=UTC)
    removed_at = datetime(2025, 4, 1, 9, tzinfo=UTC)
    restored_at = datetime(2025, 5, 1, 9, tzinfo=UTC)

    first = refresh_employee_assignments(
        db,
        employee,
        first_at.date(),
        first_at,
    )[0]
    first_id = first.id

    unchanged = refresh_employee_assignments(
        db,
        employee,
        unchanged_at.date(),
        unchanged_at,
    )[0]
    assert unchanged.id == first_id
    assert ensure_utc(unchanged.effective_from) == first_at

    policy.versions[0].values[0].value = "biweekly"
    db.flush()
    changed = refresh_employee_assignments(
        db,
        employee,
        changed_at.date(),
        changed_at,
    )[0]
    assert changed.id != first_id
    assert changed.value == "biweekly"

    employee.policies = []
    db.flush()
    assert refresh_employee_assignments(
        db,
        employee,
        removed_at.date(),
        removed_at,
    ) == []

    policy.versions[0].values[0].value = "weekly"
    employee.policies = [policy]
    db.flush()
    restored = refresh_employee_assignments(
        db,
        employee,
        restored_at.date(),
        restored_at,
    )[0]
    assert restored.value == "weekly"
    assert restored.id != first_id

    history = get_employee_assignment_history(db, employee.id)
    assert [item.value for item in history] == ["weekly", "biweekly", "weekly"]
    assert history[0].effective_until is not None
    assert ensure_utc(history[0].effective_until) == changed_at
    assert history[1].effective_until is not None
    assert ensure_utc(history[1].effective_until) == removed_at
    assert history[2].effective_until is None

    assert [
        item.value
        for item in get_employee_assignments_as_of(db, employee.id, first_at)
    ] == ["weekly"]
    assert [
        item.value
        for item in get_employee_assignments_as_of(db, employee.id, changed_at)
    ] == ["biweekly"]
    assert get_employee_assignments_as_of(db, employee.id, removed_at) == []
    assert [
        item.value
        for item in get_employee_assignments_as_of(db, employee.id, restored_at)
    ] == ["weekly"]


def test_same_value_from_a_new_source_creates_history(db):
    employee = make_employee()
    field = FieldDefinition(name="badge", cardinality="one")
    first_policy = make_policy("First", field, "blue", priority=10)
    second_policy = make_policy("Second", field, "blue", priority=20)
    employee.policies = [first_policy]
    db.add_all([employee, second_policy])
    db.flush()

    first_at = datetime(2025, 1, 1, tzinfo=UTC)
    second_at = datetime(2025, 2, 1, tzinfo=UTC)
    first = refresh_employee_assignments(db, employee, first_at.date(), first_at)[0]

    employee.policies.append(second_policy)
    db.flush()
    second = refresh_employee_assignments(
        db,
        employee,
        second_at.date(),
        second_at,
    )[0]

    assert first.value == second.value == "blue"
    assert first.source_policy_version_id != second.source_policy_version_id
    assert first.effective_until is not None
    assert ensure_utc(first.effective_until) == second_at
    assert second.effective_until is None


def test_many_assignments_are_diffed_independently(db):
    employee = make_employee()
    field = FieldDefinition(name="application_access", cardinality="many")
    version = PolicyVersion(
        version_number=1,
        priority=10,
        effective_from=date(2020, 1, 1),
        values=[
            PolicyFieldValue(field_definition=field, value="GitHub"),
            PolicyFieldValue(field_definition=field, value="Slack"),
        ],
    )
    employee.policies = [Policy(name="Applications", versions=[version])]
    db.add(employee)
    db.flush()

    first_at = datetime(2025, 1, 1, tzinfo=UTC)
    changed_at = datetime(2025, 2, 1, tzinfo=UTC)
    first = refresh_employee_assignments(db, employee, first_at.date(), first_at)
    github_id = next(item.id for item in first if item.value == "GitHub")

    slack = next(item for item in version.values if item.value == "Slack")
    version.values.remove(slack)
    version.values.append(PolicyFieldValue(field_definition=field, value="Figma"))
    db.flush()
    changed = refresh_employee_assignments(db, employee, changed_at.date(), changed_at)

    assert {item.value for item in changed} == {"GitHub", "Figma"}
    assert next(item.id for item in changed if item.value == "GitHub") == github_id
    history = list(
        db.scalars(
            select(EmployeeAssignment).order_by(EmployeeAssignment.value)
        )
    )
    by_value = {item.value: item for item in history}
    assert by_value["GitHub"].effective_until is None
    assert by_value["Figma"].effective_until is None
    assert ensure_utc(by_value["Slack"].effective_until) == changed_at


def test_same_timestamp_removal_does_not_leave_a_zero_length_row(db):
    employee = make_employee()
    field = FieldDefinition(name="badge", cardinality="one")
    employee.policies = [make_policy("Badge", field, "blue")]
    db.add(employee)
    db.flush()
    effective_at = datetime(2025, 1, 1, tzinfo=UTC)

    refresh_employee_assignments(db, employee, effective_at.date(), effective_at)
    employee.policies = []
    db.flush()
    assert refresh_employee_assignments(
        db,
        employee,
        effective_at.date(),
        effective_at,
    ) == []
    assert get_employee_assignment_history(db, employee.id) == []


def test_reconciliation_rejects_out_of_order_history(db):
    employee = make_employee()
    field = FieldDefinition(name="badge", cardinality="one")
    employee.policies = [make_policy("Badge", field, "blue")]
    db.add(employee)
    db.flush()
    later = datetime(2025, 2, 1, tzinfo=UTC)
    earlier = datetime(2025, 1, 1, tzinfo=UTC)
    refresh_employee_assignments(db, employee, later.date(), later)

    with pytest.raises(AssignmentReconciliationOrderError):
        refresh_employee_assignments(db, employee, earlier.date(), earlier)
