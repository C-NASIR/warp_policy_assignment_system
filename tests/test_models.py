from sqlalchemy import inspect

from app.database import Base
from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Condition,
    ConditionGroup,
    ConditionGroupCondition,
    EmployeePolicy,
    FieldDefinition,
    Policy,
    PolicyFieldValue,
)


def test_policy_domain_models_have_required_columns():
    expected = {
        Policy: {"id", "name", "priority"},
        CompiledPolicyClause: {"id", "policy_id"},
        CompiledPolicyCondition: {"id", "clause_id", "field", "operator", "value"},
        Condition: {"id", "field", "operator", "value"},
        ConditionGroup: {"id", "policy_id", "parent_group_id", "logical_operator"},
        ConditionGroupCondition: {"group_id", "condition_id"},
        EmployeePolicy: {"employee_id", "policy_id"},
        FieldDefinition: {"id", "field", "cardinality", "conflict_resolution"},
        PolicyFieldValue: {"policy_id", "field_definition_id", "value"},
    }

    for model, required_columns in expected.items():
        actual_columns = {column.key for column in inspect(model).columns}
        assert required_columns <= actual_columns


def test_join_models_use_composite_primary_keys():
    group_condition_pk = {column.key for column in inspect(ConditionGroupCondition).primary_key}
    employee_policy_pk = {column.key for column in inspect(EmployeePolicy).primary_key}
    policy_value_pk = {column.key for column in inspect(PolicyFieldValue).primary_key}

    assert group_condition_pk == {"group_id", "condition_id"}
    assert employee_policy_pk == {"employee_id", "policy_id"}
    assert policy_value_pk == {"policy_id", "field_definition_id", "value"}


def test_legacy_group_models_and_columns_are_absent():
    assert "groups" not in Base.metadata.tables
    assert "employee_groups" not in Base.metadata.tables
    assert "group_id" not in {column.key for column in inspect(Policy).columns}
