from dataclasses import dataclass

from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    ConditionFieldDefinition,
    ConditionGroup,
)
from app.policy_condition_limits import MAX_COMPILED_CLAUSES


class PolicyCompilationError(ValueError):
    pass


@dataclass(frozen=True)
class CompiledCondition:
    condition_field_definition: ConditionFieldDefinition
    operator: str
    value: str

    @property
    def field(self) -> str:
        return self.condition_field_definition.key


CompiledClause = tuple[CompiledCondition, ...]


def compile_condition_tree_to_clauses(root: ConditionGroup) -> list[CompiledClause]:
    """Compile a nested condition tree into disjunctive normal form.

    Each returned tuple is an AND clause. The list of tuples is joined by OR.
    For example, ``A AND (B OR C)`` becomes ``[(A, B), (A, C)]``.
    """
    return _compile_group(root, ancestors=set())


def compile_policy_version_clauses(canonical_root: ConditionGroup) -> list[CompiledPolicyClause]:
    """Build flat matching clauses for one version's canonical condition tree."""
    compiled_clauses = compile_condition_tree_to_clauses(canonical_root)
    return [
        CompiledPolicyClause(
            conditions=[
                CompiledPolicyCondition(
                    condition_field_definition=condition.condition_field_definition,
                    operator=condition.operator,
                    value=condition.value,
                )
                for condition in clause
            ]
        )
        for clause in compiled_clauses
    ]


def _compile_group(root: ConditionGroup, ancestors: set[int]) -> list[CompiledClause]:
    identity = id(root)
    if identity in ancestors:
        raise PolicyCompilationError("Condition groups must not contain cycles")

    next_ancestors = ancestors | {identity}
    operands: list[list[CompiledClause]] = [
        [
            (
                CompiledCondition(
                    link.condition.condition_field_definition,
                    link.condition.operator,
                    link.condition.value,
                ),
            )
        ]
        for link in root.condition_links
    ]
    operands.extend(_compile_group(child, next_ancestors) for child in root.child_groups)

    if not operands:
        raise PolicyCompilationError("Condition groups must contain a condition or child group")

    if root.logical_operator == "or":
        clause_count = sum(len(operand) for operand in operands)
        _require_clause_limit(clause_count)
        return [clause for operand in operands for clause in operand]
    if root.logical_operator == "and":
        clauses: list[CompiledClause] = [()]
        for operand in operands:
            _require_clause_limit(len(clauses) * len(operand))
            clauses = [left + right for left in clauses for right in operand]
        return clauses

    raise PolicyCompilationError(f"Unsupported logical operator: {root.logical_operator}")


def _require_clause_limit(clause_count: int) -> None:
    if clause_count > MAX_COMPILED_CLAUSES:
        raise PolicyCompilationError(
            f"A policy may compile to at most {MAX_COMPILED_CLAUSES} clauses"
        )
