from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.policy_condition_limits import (
    MAX_COMPILED_CLAUSES,
    MAX_CONDITION_GROUP_DEPTH,
    MAX_CONDITION_GROUPS,
    MAX_POLICY_CONDITIONS,
    condition_tree_stats,
)
from app.schemas import ConditionGroupCreate, PolicyVersionCreate
from app.services.policy_compiler import (
    PolicyCompilationError,
    compile_condition_tree_to_clauses,
)


def condition(value: str = "CA") -> dict[str, str]:
    return {"field": "state", "operator": "=", "value": value}


def group(
    *,
    operator: str = "and",
    conditions: list[dict[str, str]] | None = None,
    children: list[dict] | None = None,
) -> dict:
    return {
        "logical_operator": operator,
        "conditions": conditions or [],
        "child_groups": children or [],
    }


def version(condition_group: dict) -> PolicyVersionCreate:
    return PolicyVersionCreate(
        priority=1,
        effective_from=date(2026, 1, 1),
        condition_group=condition_group,
        values=[{"assignment_field_definition_id": 1, "value": "test"}],
    )


def test_accepts_limits_at_the_documented_boundaries():
    deepest = group(conditions=[condition()])
    for _ in range(MAX_CONDITION_GROUP_DEPTH - 1):
        deepest = group(children=[deepest])

    data = version(deepest)

    stats = condition_tree_stats(data.condition_group)
    assert stats.depth == MAX_CONDITION_GROUP_DEPTH
    assert stats.groups == MAX_CONDITION_GROUP_DEPTH
    assert stats.conditions == 1
    assert stats.compiled_clauses == 1


def test_rejects_a_condition_tree_beyond_the_maximum_depth():
    deepest = group(conditions=[condition()])
    for _ in range(MAX_CONDITION_GROUP_DEPTH):
        deepest = group(children=[deepest])

    with pytest.raises(
        ValidationError,
        match=f"at most {MAX_CONDITION_GROUP_DEPTH} levels deep",
    ):
        version(deepest)


def test_rejects_too_many_groups_or_conditions():
    too_many_groups = group(
        children=[
            group(conditions=[condition()]) for _ in range(MAX_CONDITION_GROUPS)
        ]
    )
    with pytest.raises(
        ValidationError,
        match=f"at most {MAX_CONDITION_GROUPS} condition groups",
    ):
        version(too_many_groups)

    too_many_conditions = group(
        conditions=[condition() for _ in range(MAX_POLICY_CONDITIONS + 1)]
    )
    with pytest.raises(
        ValidationError,
        match=f"at most {MAX_POLICY_CONDITIONS} conditions",
    ):
        version(too_many_conditions)


def test_rejects_condition_trees_that_expand_into_too_many_clauses():
    expanding_tree = group(
        children=[
            group(
                operator="or",
                conditions=[condition("CA"), condition("NY"), condition("TX")],
            )
            for _ in range(5)
        ]
    )

    with pytest.raises(
        ValidationError,
        match=f"at most {MAX_COMPILED_CLAUSES} clauses",
    ):
        version(expanding_tree)


def test_counts_an_or_of_and_groups_as_one_clause_per_group():
    rule_sets = ConditionGroupCreate.model_validate(
        group(
            operator="or",
            children=[
                group(conditions=[condition("CA"), condition("NY")]),
                group(conditions=[condition("TX"), condition("CA")]),
            ],
        )
    )

    assert condition_tree_stats(rule_sets).compiled_clauses == 2


def test_compiler_stops_clause_expansion_even_without_request_validation():
    definition = SimpleNamespace(key="state")

    def compiled_or_group():
        return SimpleNamespace(
            logical_operator="or",
            condition_links=[
                SimpleNamespace(
                    condition=SimpleNamespace(
                        condition_field_definition=definition,
                        operator="=",
                        value=value,
                    )
                )
                for value in ("CA", "NY", "TX")
            ],
            child_groups=[],
        )

    root = SimpleNamespace(
        logical_operator="and",
        condition_links=[],
        child_groups=[compiled_or_group() for _ in range(5)],
    )

    with pytest.raises(
        PolicyCompilationError,
        match=f"at most {MAX_COMPILED_CLAUSES} clauses",
    ):
        compile_condition_tree_to_clauses(root)
