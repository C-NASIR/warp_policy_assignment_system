from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


MAX_CONDITION_GROUP_DEPTH = 3
MAX_CONDITION_GROUPS = 20
MAX_POLICY_CONDITIONS = 50
MAX_COMPILED_CLAUSES = 200


class ConditionGroupLike(Protocol):
    logical_operator: str
    conditions: list
    child_groups: list[ConditionGroupLike]


@dataclass(frozen=True)
class ConditionTreeStats:
    groups: int
    conditions: int
    depth: int
    compiled_clauses: int


def condition_tree_stats(root: ConditionGroupLike) -> ConditionTreeStats:
    """Return bounded structural and compilation counts for a condition tree."""
    groups, conditions, depth = _structural_stats(root, depth=1)
    return ConditionTreeStats(
        groups=groups,
        conditions=conditions,
        depth=depth,
        compiled_clauses=_compiled_clause_count(root),
    )


def validate_condition_tree_limits(root: ConditionGroupLike) -> None:
    stats = condition_tree_stats(root)
    if stats.depth > MAX_CONDITION_GROUP_DEPTH:
        raise ValueError(
            f"Condition groups may be at most {MAX_CONDITION_GROUP_DEPTH} levels deep"
        )
    if stats.groups > MAX_CONDITION_GROUPS:
        raise ValueError(
            f"A policy may contain at most {MAX_CONDITION_GROUPS} condition groups"
        )
    if stats.conditions > MAX_POLICY_CONDITIONS:
        raise ValueError(
            f"A policy may contain at most {MAX_POLICY_CONDITIONS} conditions"
        )
    if stats.compiled_clauses > MAX_COMPILED_CLAUSES:
        raise ValueError(
            f"A policy may compile to at most {MAX_COMPILED_CLAUSES} clauses"
        )


def _structural_stats(
    root: ConditionGroupLike,
    *,
    depth: int,
) -> tuple[int, int, int]:
    group_count = 1
    condition_count = len(root.conditions)
    maximum_depth = depth
    for child in root.child_groups:
        child_groups, child_conditions, child_depth = _structural_stats(
            child,
            depth=depth + 1,
        )
        group_count += child_groups
        condition_count += child_conditions
        maximum_depth = max(maximum_depth, child_depth)
    return group_count, condition_count, maximum_depth


def _compiled_clause_count(root: ConditionGroupLike) -> int:
    operand_counts = [1] * len(root.conditions)
    operand_counts.extend(_compiled_clause_count(child) for child in root.child_groups)
    if not operand_counts:
        return 0
    if root.logical_operator == "or":
        return min(sum(operand_counts), MAX_COMPILED_CLAUSES + 1)

    clause_count = 1
    for operand_count in operand_counts:
        clause_count *= operand_count
        if clause_count > MAX_COMPILED_CLAUSES:
            return MAX_COMPILED_CLAUSES + 1
    return clause_count
