from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    ConditionGroup,
    Policy,
)


class PolicyCompilationError(ValueError):
    pass


@dataclass(frozen=True)
class CompiledCondition:
    field: str
    operator: str
    value: str


CompiledClause = tuple[CompiledCondition, ...]


def compile_condition_tree(root: ConditionGroup) -> list[CompiledClause]:
    """Compile a nested condition tree into disjunctive normal form.

    Each returned tuple is an AND clause. The list of tuples is joined by OR.
    For example, ``A AND (B OR C)`` becomes ``[(A, B), (A, C)]``.
    """
    return _compile_group(root, ancestors=set())


def recompile_policy(session: Session, policy: Policy) -> list[CompiledPolicyClause]:
    """Replace a policy's persisted compiled clauses within the current transaction."""
    roots = [group for group in policy.condition_groups if group.parent_group is None]
    if len(roots) != 1:
        raise PolicyCompilationError(
            f"Policy {policy.id} must have exactly one root condition group; found {len(roots)}"
        )

    compiled = compile_condition_tree(roots[0])
    policy.compiled_clauses = [
        CompiledPolicyClause(
            conditions=[
                CompiledPolicyCondition(
                    field=condition.field,
                    operator=condition.operator,
                    value=condition.value,
                )
                for condition in clause
            ]
        )
        for clause in compiled
    ]
    session.flush()
    return policy.compiled_clauses


def _compile_group(root: ConditionGroup, ancestors: set[int]) -> list[CompiledClause]:
    identity = id(root)
    if identity in ancestors:
        raise PolicyCompilationError("Condition groups must not contain cycles")

    next_ancestors = ancestors | {identity}
    operands: list[list[CompiledClause]] = [
        [(CompiledCondition(link.condition.field, link.condition.operator, link.condition.value),)]
        for link in root.condition_links
    ]
    operands.extend(_compile_group(child, next_ancestors) for child in root.child_groups)

    if not operands:
        raise PolicyCompilationError("Condition groups must contain a condition or child group")

    if root.logical_operator == "or":
        return [clause for operand in operands for clause in operand]
    if root.logical_operator == "and":
        clauses: list[CompiledClause] = [()]
        for operand in operands:
            clauses = [left + right for left in clauses for right in operand]
        return clauses

    raise PolicyCompilationError(f"Unsupported logical operator: {root.logical_operator}")
