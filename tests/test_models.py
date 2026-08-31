from typing import cast

from sqlalchemy import CheckConstraint, Table, UniqueConstraint, inspect

from app.database import Base
from app.models import (
    AuditLog,
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Condition,
    ConditionFieldDefinition,
    ConditionFieldDependency,
    ConditionGroup,
    ConditionGroupCondition,
    Employee,
    EmployeeAssignment,
    EmployeeGroupMembership,
    EmployeeOverride,
    EmployeePolicy,
    AssignmentFieldDefinition,
    Group,
    GroupPolicy,
    Policy,
    PolicyFieldValue,
    PolicyVersion,
    ScheduledReconciliation,
)


def test_policy_domain_models_have_required_columns():
    expected = {
        AuditLog: {
            "id",
            "actor",
            "entity_type",
            "entity_id",
            "action",
            "before",
            "after",
            "timestamp",
        },
        ScheduledReconciliation: {
            "id",
            "entity_type",
            "entity_id",
            "trigger_type",
            "scheduled_at",
            "status",
            "processed_at",
        },
        Employee: {
            "id",
            "name",
            "state",
            "department",
            "employee_type",
            "location",
            "start_date",
            "manager_id",
        },
        Policy: {"id", "name", "status", "created_at"},
        PolicyVersion: {
            "id",
            "policy_id",
            "version_number",
            "priority",
            "effective_from",
            "effective_until",
            "created_at",
            "created_by",
        },
        CompiledPolicyClause: {"id", "policy_version_id"},
        ConditionFieldDefinition: {
            "id",
            "key",
            "label",
            "field_type",
            "data_type",
            "resolver_key",
            "source_table",
            "source_column",
            "active",
        },
        ConditionFieldDependency: {
            "id",
            "condition_field_definition_id",
            "dependency_type",
            "dependency_key",
            "source_table",
            "source_column",
            "role",
            "impact_resolver_key",
        },
        CompiledPolicyCondition: {
            "id",
            "clause_id",
            "condition_field_definition_id",
            "operator",
            "value",
        },
        Condition: {
            "id",
            "condition_field_definition_id",
            "operator",
            "value",
        },
        ConditionGroup: {
            "id",
            "policy_version_id",
            "parent_group_id",
            "logical_operator",
        },
        ConditionGroupCondition: {"group_id", "condition_id"},
        Group: {"id", "name"},
        EmployeeGroupMembership: {"employee_id", "group_id"},
        GroupPolicy: {"group_id", "policy_id"},
        EmployeePolicy: {"employee_id", "policy_id"},
        EmployeeOverride: {
            "id",
            "employee_id",
            "assignment_field_definition_id",
            "value",
            "retired_at",
        },
        EmployeeAssignment: {
            "id",
            "employee_id",
            "assignment_field_definition_id",
            "value",
            "source_policy_version_id",
            "source_override_id",
            "effective_from",
            "effective_until",
        },
        AssignmentFieldDefinition: {"id", "field", "cardinality", "conflict_resolution"},
        PolicyFieldValue: {"policy_version_id", "assignment_field_definition_id", "value"},
    }

    for model, required_columns in expected.items():
        actual_columns = {column.key for column in inspect(model).columns}
        assert required_columns <= actual_columns


def test_join_models_use_composite_primary_keys():
    group_condition_pk = {column.key for column in inspect(ConditionGroupCondition).primary_key}
    employee_group_pk = {column.key for column in inspect(EmployeeGroupMembership).primary_key}
    group_policy_pk = {column.key for column in inspect(GroupPolicy).primary_key}
    employee_policy_pk = {column.key for column in inspect(EmployeePolicy).primary_key}
    policy_value_pk = {column.key for column in inspect(PolicyFieldValue).primary_key}

    assert group_condition_pk == {"group_id", "condition_id"}
    assert employee_group_pk == {"employee_id", "group_id"}
    assert group_policy_pk == {"group_id", "policy_id"}
    assert employee_policy_pk == {"employee_id", "policy_id"}
    assert policy_value_pk == {"policy_version_id", "assignment_field_definition_id", "value"}


def test_legacy_group_columns_are_absent():
    assert "groups" in Base.metadata.tables
    assert "employee_group_memberships" in Base.metadata.tables
    assert "group_policies" in Base.metadata.tables
    assert "employee_groups" not in Base.metadata.tables
    assert "group_id" not in {column.key for column in inspect(Policy).columns}


def test_employee_assignment_requires_exactly_one_source():
    assignment_table = cast(Table, EmployeeAssignment.__table__)
    constraints = {
        constraint.name
        for constraint in assignment_table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_employee_assignment_exactly_one_source" in constraints
    assert "ck_employee_assignment_valid_effective_range" in constraints


def test_policy_versions_enforce_number_and_effective_range_constraints():
    policy_version_table = cast(Table, PolicyVersion.__table__)
    unique_columns = {
        column.key
        for constraint in policy_version_table.constraints
        if isinstance(constraint, UniqueConstraint)
        for column in constraint.columns
    }
    check_names = {
        constraint.name
        for constraint in policy_version_table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert unique_columns == {"policy_id", "version_number"}
    assert "ck_policy_version_valid_effective_range" in check_names


def test_scheduled_reconciliations_enforce_lifecycle_and_lookup_indexes():
    table = cast(Table, ScheduledReconciliation.__table__)
    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    unique_column_sets = {
        tuple(column.key for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    index_names = {index.name for index in table.indexes}

    assert {
        "ck_scheduled_reconciliation_status",
        "ck_scheduled_reconciliation_processed_at",
    } <= check_names
    assert (
        "entity_type",
        "entity_id",
        "trigger_type",
        "scheduled_at",
    ) in unique_column_sets
    assert {
        "ix_scheduled_reconciliations_due",
        "ix_scheduled_reconciliations_entity",
    } <= index_names


def test_group_relationships_persist_memberships_and_policies(db):
    employee = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    policy = Policy(name="GitHub Access")
    group = Group(name="Engineering", employees=[employee], policies=[policy])
    db.add(group)
    db.flush()

    membership = db.get(EmployeeGroupMembership, (employee.id, group.id))
    group_policy = db.get(GroupPolicy, (group.id, policy.id))

    assert membership is not None
    assert group_policy is not None
    assert employee.groups == [group]
    assert policy.groups == [group]


def test_deleting_group_removes_links_without_deleting_employees_or_policies(db):
    employee = Employee(
        name="Alice",
        state="California",
        department="Engineering",
        employee_type="regular",
    )
    policy = Policy(name="GitHub Access")
    group = Group(name="Engineering", employees=[employee], policies=[policy])
    db.add(group)
    db.flush()
    employee_id = employee.id
    policy_id = policy.id
    group_id = group.id

    db.delete(group)
    db.flush()

    assert db.get(EmployeeGroupMembership, (employee_id, group_id)) is None
    assert db.get(GroupPolicy, (group_id, policy_id)) is None
    assert db.get(Employee, employee_id) is not None
    assert db.get(Policy, policy_id) is not None
