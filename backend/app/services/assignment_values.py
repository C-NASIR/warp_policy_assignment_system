from __future__ import annotations

from app.models import AssignmentFieldDefinition


class AssignmentValueError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        assignment_field_definition_id: int,
        assignment_field_name: str,
        value: str,
    ) -> None:
        super().__init__(message)
        self.metadata = {
            "assignment_field_definition_id": assignment_field_definition_id,
            "assignment_field_name": assignment_field_name,
            "value": value,
        }


def normalize_assignment_value(
    definition: AssignmentFieldDefinition,
    value: str,
) -> str:
    normalized = value.strip()
    if not normalized:
        raise AssignmentValueError(
            f"Assignment value for field '{definition.name}' must not be blank",
            assignment_field_definition_id=definition.id,
            assignment_field_name=definition.name,
            value=value,
        )
    input_definition = definition.input or {"type": "text", "options": []}
    if input_definition.get("type") == "select":
        allowed = {
            str(option["value"]): str(option["value"])
            for option in input_definition.get("options", [])
        }
        if normalized not in allowed:
            raise AssignmentValueError(
                f"Value '{normalized}' is not an allowed option for field "
                f"'{definition.name}'",
                assignment_field_definition_id=definition.id,
                assignment_field_name=definition.name,
                value=normalized,
            )
        return allowed[normalized]
    return normalized
