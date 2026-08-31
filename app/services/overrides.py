from dataclasses import dataclass

from app.models import EmployeeOverride
from app.services.policy_engine import ResolvedAssignment


@dataclass(frozen=True)
class FinalAssignment:
    assignment_field_definition_id: int
    value: str
    source_policy_version_id: int | None = None
    source_override_id: int | None = None


def apply_employee_overrides(
    resolved_assignments: list[ResolvedAssignment],
    overrides: list[EmployeeOverride],
) -> list[FinalAssignment]:
    """Replace every policy value for an overridden field with its override values."""
    overridden_field_ids = {override.assignment_field_definition_id for override in overrides}
    final = [
        FinalAssignment(
            assignment_field_definition_id=item.assignment_field_definition_id,
            value=item.value,
            source_policy_version_id=item.source_policy_version_id,
        )
        for item in resolved_assignments
        if item.assignment_field_definition_id not in overridden_field_ids
    ]
    final.extend(
        FinalAssignment(
            assignment_field_definition_id=override.assignment_field_definition_id,
            value=override.value,
            source_override_id=override.id,
        )
        for override in overrides
    )
    return sorted(final, key=lambda item: (item.assignment_field_definition_id, item.value))
