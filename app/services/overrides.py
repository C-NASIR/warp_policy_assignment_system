from dataclasses import dataclass

from app.models import EmployeeOverride
from app.services.policy_engine import ResolvedAssignment


@dataclass(frozen=True)
class FinalAssignment:
    field_definition_id: int
    value: str
    source_policy_id: int | None = None
    source_override_id: int | None = None


def apply_employee_overrides(
    resolved_assignments: list[ResolvedAssignment],
    overrides: list[EmployeeOverride],
) -> list[FinalAssignment]:
    """Replace every policy value for an overridden field with its override values."""
    overridden_field_ids = {override.field_definition_id for override in overrides}
    final = [
        FinalAssignment(
            field_definition_id=item.field_definition_id,
            value=item.value,
            source_policy_id=item.source_policy_id,
        )
        for item in resolved_assignments
        if item.field_definition_id not in overridden_field_ids
    ]
    final.extend(
        FinalAssignment(
            field_definition_id=override.field_definition_id,
            value=override.value,
            source_override_id=override.id,
        )
        for override in overrides
    )
    return sorted(final, key=lambda item: (item.field_definition_id, item.value))
