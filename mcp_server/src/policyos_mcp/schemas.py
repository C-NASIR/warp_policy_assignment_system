from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PositiveId = Annotated[int, Field(gt=0)]
GroupName = Annotated[str, Field(min_length=1, max_length=200)]
TemporaryPassword = Annotated[str, Field(min_length=12, max_length=128)]


class ToolInput(BaseModel):
    """Strict base model for payloads exposed through MCP tool schemas."""

    model_config = ConfigDict(extra="forbid")


class EmployeeCreateInput(ToolInput):
    name: str = Field(min_length=1, max_length=200)
    state: str = Field(min_length=2, max_length=2)
    department: str = Field(min_length=1, max_length=100)
    employee_type: str = Field(min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date = Field(default_factory=date.today)
    manager_id: PositiveId | None = None


class EmployeeUpdateInput(ToolInput):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    employee_type: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    manager_id: PositiveId | None = None

    @model_validator(mode="after")
    def require_supported_change(self) -> EmployeeUpdateInput:
        if not self.model_fields_set:
            raise ValueError("At least one employee field must be provided")
        nullable_fields = {"location", "manager_id"}
        for field_name in self.model_fields_set - nullable_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class AssignmentQueryInput(ToolInput):
    employee_ids: list[PositiveId] = Field(min_length=1, max_length=1000)
    evaluation_date: date

    @field_validator("employee_ids")
    @classmethod
    def require_unique_employee_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("employee_ids must be unique")
        return value


class EmployeeOverrideCreateInput(ToolInput):
    assignment_field_definition_id: PositiveId
    value: str = Field(min_length=1, max_length=500)


class EmployeeOverrideUpdateInput(ToolInput):
    assignment_field_definition_id: PositiveId | None = None
    value: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_override_change(self) -> EmployeeOverrideUpdateInput:
        if not self.model_fields_set:
            raise ValueError("At least one override field must be provided")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class AssignmentFieldOptionInput(ToolInput):
    value: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=200)


class AssignmentFieldValueInput(ToolInput):
    type: Literal["text", "select"] = "text"
    options: list[AssignmentFieldOptionInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_options(self) -> AssignmentFieldValueInput:
        if self.type == "select" and not self.options:
            raise ValueError("Select assignment fields require at least one option")
        if self.type == "text" and self.options:
            raise ValueError("Text assignment fields cannot define options")
        values = [option.value.casefold() for option in self.options]
        if len(values) != len(set(values)):
            raise ValueError("Assignment field option values must be unique")
        return self


class AssignmentFieldCreateInput(ToolInput):
    name: str = Field(min_length=1, max_length=100)
    cardinality: Literal["one", "many"]
    conflict_resolution: str = Field(default="priority", min_length=1, max_length=50)
    input: AssignmentFieldValueInput = Field(default_factory=AssignmentFieldValueInput)


class AssignmentFieldUpdateInput(ToolInput):
    input: AssignmentFieldValueInput


class PolicyValueInput(ToolInput):
    assignment_field_definition_id: PositiveId
    value: str = Field(min_length=1, max_length=500)


class ConditionInput(ToolInput):
    field: str = Field(min_length=1, max_length=100)
    operator: Literal["=", "<", "<=", ">", ">="]
    value: str = Field(min_length=1, max_length=500)


class ConditionGroupInput(ToolInput):
    logical_operator: Literal["and", "or"]
    conditions: list[ConditionInput] = Field(default_factory=list)
    child_groups: list[ConditionGroupInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_operand(self) -> ConditionGroupInput:
        if not self.conditions and not self.child_groups:
            raise ValueError(
                "A condition group must contain a condition or child group"
            )
        return self


class PolicyVersionInput(ToolInput):
    priority: int
    effective_from: date = Field(default_factory=date.today)
    effective_until: date | None = None
    created_by: str | None = Field(default=None, min_length=1, max_length=200)
    condition_group: ConditionGroupInput
    values: list[PolicyValueInput] = Field(min_length=1)

    @model_validator(mode="after")
    def require_valid_effective_range(self) -> PolicyVersionInput:
        if (
            self.effective_until is not None
            and self.effective_until < self.effective_from
        ):
            raise ValueError("effective_until cannot be before effective_from")
        return self


class PolicyCreateInput(PolicyVersionInput):
    name: str = Field(min_length=1, max_length=200)
    status: Literal["draft", "active", "archived"] = "active"


class PolicyUpdateInput(ToolInput):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["draft", "active", "archived"] | None = None

    @model_validator(mode="after")
    def require_policy_change(self) -> PolicyUpdateInput:
        if not self.model_fields_set:
            raise ValueError("At least one policy field must be provided")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class RoleCreateInput(ToolInput):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list)
    employee_scope: Literal["all", "reporting_tree", "self", "none"] = "none"
    assignment_field_scope: Literal["all", "selected", "none"] = "none"
    assignment_field_ids: list[PositiveId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_assignment_field_scope(self) -> RoleCreateInput:
        if self.assignment_field_scope == "selected" and not self.assignment_field_ids:
            raise ValueError(
                "Selected assignment fields must include at least one field"
            )
        if self.assignment_field_scope != "selected" and self.assignment_field_ids:
            raise ValueError("Assignment field IDs are only valid for selected scope")
        return self


class RoleUpdateInput(ToolInput):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] | None = None
    employee_scope: Literal["all", "reporting_tree", "self", "none"] | None = None
    assignment_field_scope: Literal["all", "selected", "none"] | None = None
    assignment_field_ids: list[PositiveId] | None = None

    @model_validator(mode="after")
    def require_role_change(self) -> RoleUpdateInput:
        if not self.model_fields_set:
            raise ValueError("At least one role field must be provided")
        return self


class UserCreateInput(ToolInput):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    temporary_password: str = Field(min_length=12, max_length=128)
    role_ids: list[PositiveId] = Field(min_length=1)
    employee_id: PositiveId | None = None


class UserUpdateInput(ToolInput):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "suspended", "disabled"] | None = None
    role_ids: list[PositiveId] | None = None
    employee_id: PositiveId | None = None

    @model_validator(mode="after")
    def require_user_change(self) -> UserUpdateInput:
        if not self.model_fields_set:
            raise ValueError("At least one user field must be provided")
        return self


class EmployeeCreatePreviewInput(ToolInput):
    type: Literal["employee_create"]
    employee: EmployeeCreateInput


class EmployeeUpdatePreviewInput(ToolInput):
    type: Literal["employee_update"]
    employee_id: PositiveId
    changes: EmployeeUpdateInput


class PolicyCreatePreviewInput(ToolInput):
    type: Literal["policy_create"]
    policy: PolicyCreateInput


class PolicyVersionCreatePreviewInput(ToolInput):
    type: Literal["policy_version_create"]
    policy_id: PositiveId
    version: PolicyVersionInput


class PolicyStatusPreviewInput(ToolInput):
    type: Literal["policy_status_change"]
    policy_id: PositiveId
    status: Literal["draft", "active", "archived"]


class GroupMembershipPreviewInput(ToolInput):
    type: Literal["group_membership_change"]
    action: Literal["add", "remove"]
    group_id: PositiveId
    employee_id: PositiveId


class EmployeeOverridePreviewInput(ToolInput):
    type: Literal["employee_override_change"]
    action: Literal["create", "update", "delete"]
    employee_id: PositiveId
    override_id: PositiveId | None = None
    assignment_field_definition_id: PositiveId | None = None
    value: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_action_fields(self) -> EmployeeOverridePreviewInput:
        if self.action == "create":
            if self.override_id is not None:
                raise ValueError(
                    "override_id is not accepted when creating an override"
                )
            if self.assignment_field_definition_id is None or self.value is None:
                raise ValueError(
                    "Creating an override requires assignment_field_definition_id and value"
                )
        elif self.action == "update":
            if self.override_id is None:
                raise ValueError("Updating an override requires override_id")
            if self.assignment_field_definition_id is None and self.value is None:
                raise ValueError(
                    "Updating an override requires assignment_field_definition_id or value"
                )
        elif self.override_id is None:
            raise ValueError("Deleting an override requires override_id")
        return self


ChangePreviewInput = Annotated[
    EmployeeCreatePreviewInput
    | EmployeeUpdatePreviewInput
    | PolicyCreatePreviewInput
    | PolicyVersionCreatePreviewInput
    | PolicyStatusPreviewInput
    | GroupMembershipPreviewInput
    | EmployeeOverridePreviewInput,
    Field(discriminator="type"),
]
