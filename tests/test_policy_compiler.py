import pytest
from sqlalchemy import func, select

from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Condition,
    ConditionGroup,
    ConditionGroupCondition,
    Policy,
)
from app.services.policy_compiler import (
    CompiledCondition,
    PolicyCompilationError,
    compile_condition_tree,
    recompile_policy,
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

    assert compile_condition_tree(root) == [
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

    clauses = compile_condition_tree(group("and", children=(left, right)))

    assert len(clauses) == 4
    assert {tuple((item.field, item.value) for item in clause) for clause in clauses} == {
        (("state", "California"), ("department", "Engineering")),
        (("state", "California"), ("department", "Sales")),
        (("state", "Wisconsin"), ("department", "Engineering")),
        (("state", "Wisconsin"), ("department", "Sales")),
    }


def test_rejects_empty_condition_group():
    with pytest.raises(PolicyCompilationError, match="must contain"):
        compile_condition_tree(group("and"))


def test_rejects_unknown_logical_operator():
    with pytest.raises(PolicyCompilationError, match="Unsupported logical operator"):
        compile_condition_tree(group("xor", condition("state", "California")))


def test_recompile_policy_persists_and_replaces_compiled_clauses(db):
    policy = Policy(name="California regular engineer", priority=10)
    a = condition("state", "California")
    b = condition("employee_type", "regular")
    c = condition("department", "Engineering")
    nested = group("or", b, c)
    root = group("and", a, children=(nested,))
    root.policy = policy
    nested.policy = policy
    db.add(policy)
    db.flush()

    clauses = recompile_policy(db, policy)

    assert len(clauses) == 2
    assert {
        frozenset((item.field, item.operator, item.value) for item in clause.conditions)
        for clause in clauses
    } == {
        frozenset({("state", "=", "California"), ("employee_type", "=", "regular")}),
        frozenset({("state", "=", "California"), ("department", "=", "Engineering")}),
    }

    root.logical_operator = "or"
    replacement = recompile_policy(db, policy)

    assert len(replacement) == 3
    assert db.scalar(select(func.count()).select_from(CompiledPolicyClause)) == 3
    assert db.scalar(select(func.count()).select_from(CompiledPolicyCondition)) == 3


def test_recompile_policy_requires_one_root_group(db):
    policy = Policy(name="No conditions", priority=10)
    db.add(policy)
    db.flush()

    with pytest.raises(PolicyCompilationError, match="exactly one root"):
        recompile_policy(db, policy)
