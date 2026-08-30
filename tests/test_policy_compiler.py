from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Condition,
    ConditionGroup,
    ConditionGroupCondition,
    Policy,
    PolicyVersion,
)
from app.services.policy_compiler import (
    CompiledCondition,
    PolicyCompilationError,
    compile_condition_tree_to_clauses,
    compile_policy_version_clauses,
)


def condition(field: str, value: str) -> Condition:
    return Condition(field=field, operator="=", value=value)


def group(operator: str, *conditions: Condition, children: tuple[ConditionGroup, ...] = ()) -> ConditionGroup:
    result = ConditionGroup(logical_operator=operator)
    result.condition_links = [ConditionGroupCondition(condition=item) for item in conditions]
    result.child_groups = list(children)
    return result


def test_compiles_and_over_nested_or_to_flat_clauses():
    a = condition("state", "California")
    b = condition("employee_type", "regular")
    c = condition("department", "Engineering")
    root = group("and", a, children=(group("or", b, c),))

    assert compile_condition_tree_to_clauses(root) == [
        (
            CompiledCondition("state", "=", "California"),
            CompiledCondition("employee_type", "=", "regular"),
        ),
        (
            CompiledCondition("state", "=", "California"),
            CompiledCondition("department", "=", "Engineering"),
        ),
    ]


def test_compiles_nested_and_groups_using_cartesian_product():
    left = group("or", condition("state", "California"), condition("state", "Wisconsin"))
    right = group("or", condition("department", "Engineering"), condition("department", "Sales"))

    clauses = compile_condition_tree_to_clauses(group("and", children=(left, right)))

    assert len(clauses) == 4
    assert {tuple((item.field, item.value) for item in clause) for clause in clauses} == {
        (("state", "California"), ("department", "Engineering")),
        (("state", "California"), ("department", "Sales")),
        (("state", "Wisconsin"), ("department", "Engineering")),
        (("state", "Wisconsin"), ("department", "Sales")),
    }


def test_rejects_empty_condition_group():
    with pytest.raises(PolicyCompilationError, match="must contain"):
        compile_condition_tree_to_clauses(group("and"))


def test_rejects_unknown_logical_operator():
    with pytest.raises(PolicyCompilationError, match="Unsupported logical operator"):
        compile_condition_tree_to_clauses(group("xor", condition("state", "California")))


def test_compile_policy_version_clauses_builds_replaceable_representation(db):
    policy = Policy(name="California regular engineer")
    version = PolicyVersion(
        policy=policy,
        version_number=1,
        priority=10,
        effective_from=date(2020, 1, 1),
    )
    a = condition("state", "California")
    b = condition("employee_type", "regular")
    c = condition("department", "Engineering")
    nested = group("or", b, c)
    root = group("and", a, children=(nested,))
    root.policy_version = version
    nested.policy_version = version
    db.add(policy)
    db.flush()

    clauses = compile_policy_version_clauses(root)
    version.compiled_clauses = clauses
    db.flush()

    assert len(clauses) == 2
    assert {
        frozenset((item.field, item.operator, item.value) for item in clause.conditions)
        for clause in clauses
    } == {
        frozenset({("state", "=", "California"), ("employee_type", "=", "regular")}),
        frozenset({("state", "=", "California"), ("department", "=", "Engineering")}),
    }

    root.logical_operator = "or"
    replacement = compile_policy_version_clauses(root)
    version.compiled_clauses = replacement
    db.flush()

    assert len(replacement) == 3
    assert db.scalar(select(func.count()).select_from(CompiledPolicyClause)) == 3
    assert db.scalar(select(func.count()).select_from(CompiledPolicyCondition)) == 3
