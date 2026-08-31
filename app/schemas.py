from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dates import current_date, ensure_utc
from app.services.condition_fields import ConditionFieldError, normalize_condition


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    state: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=100)
    employee_type: str = Field(min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date = Field(default_factory=current_date)
    manager_id: int | None = Field(default=None, gt=0)


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    employee_type: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    manager_id: int | None = Field(default=None, gt=0)


class EmployeeRead(EmployeeCreate, ORMModel):
    id: int


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class GroupRead(GroupCreate, ORMModel):
    id: int


class FieldDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cardinality: Literal["one", "many"]
    conflict_resolution: str = Field(default="priority", min_length=1, max_length=50)


class FieldDefinitionRead(FieldDefinitionCreate, ORMModel):
    id: int


class ConditionFieldDependencyRead(ORMModel):
    id: int
    dependency_type: Literal["column", "relationship", "time"]
    dependency_key: str
    source_table: str | None
    source_column: str | None
    role: str
    impact_resolver_key: str


class ConditionFieldDefinitionRead(ORMModel):
    id: int
    key: str
    label: str
    field_type: Literal["static", "derived"]
    data_type: str
    resolver_key: str | None
    source_table: str | None
    source_column: str | None
    active: bool
    dependencies: list[ConditionFieldDependencyRead]


class EmployeeOverrideCreate(BaseModel):
    field_definition_id: int
    value: str = Field(min_length=1, max_length=500)


class EmployeeOverrideUpdate(BaseModel):
    field_definition_id: int | None = None
    value: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_a_change(self) -> EmployeeOverrideUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one override field must be provided")
        if "field_definition_id" in self.model_fields_set and self.field_definition_id is None:
            raise ValueError("field_definition_id cannot be null")
        if "value" in self.model_fields_set and self.value is None:
            raise ValueError("value cannot be null")
        return self


class EmployeeOverrideRead(ORMModel):
    id: int
    employee_id: int
    field_definition_id: int
    value: str
    retired_at: datetime | None
    field_definition: FieldDefinitionRead


class PolicyValueCreate(BaseModel):
    field_definition_id: int
    value: str = Field(min_length=1, max_length=500)


class ConditionCreate(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    operator: Literal["=", "<", "<=", ">", ">="]
    value: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_a_typed_fact_value(self) -> ConditionCreate:
        try:
            self.value = normalize_condition(self.field, self.operator, self.value)
        except ConditionFieldError as exc:
            raise ValueError(str(exc)) from exc
        return self


class ConditionGroupCreate(BaseModel):
    logical_operator: Literal["and", "or"]
    conditions: list[ConditionCreate] = Field(default_factory=list)
    child_groups: list[ConditionGroupCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_an_operand(self) -> ConditionGroupCreate:
        if not self.conditions and not self.child_groups:
            raise ValueError("A condition group must contain a condition or child group")
        return self


class PolicyVersionCreate(BaseModel):
    priority: int
    effective_from: date = Field(default_factory=current_date)
    effective_until: date | None = None
    created_by: str | None = Field(default=None, min_length=1, max_length=200)
    condition_group: ConditionGroupCreate
    values: list[PolicyValueCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_a_valid_effective_range(self) -> PolicyVersionCreate:
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise ValueError("effective_until cannot be before effective_from")
        return self


class PolicyCreate(PolicyVersionCreate):
    name: str = Field(min_length=1, max_length=200)
    status: Literal["active", "archived"] = "active"


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "archived"] | None = None


class PolicyValueRead(PolicyValueCreate, ORMModel):
    pass


class PolicyVersionRead(ORMModel):
    id: int
    policy_id: int
    version_number: int
    priority: int
    effective_from: date
    effective_until: date | None
    created_at: datetime
    created_by: str | None
    values: list[PolicyValueRead]


class PolicyRead(ORMModel):
    id: int
    name: str
    status: Literal["active", "archived"]
    created_at: datetime
    versions: list[PolicyVersionRead]


class AssignmentRead(ORMModel):
    id: int
    employee_id: int
    field_definition_id: int
    value: str
    source_policy_version_id: int | None
    source_override_id: int | None
    effective_from: datetime
    effective_until: datetime | None
    field_definition: FieldDefinitionRead

    @field_validator("effective_from", "effective_until", mode="before")
    @classmethod
    def return_utc_timestamps(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class AuditLogRead(ORMModel):
    id: int
    actor: str
    entity_type: str
    entity_id: int
    action: str
    before: dict[str, Any] | list[Any] | None
    after: dict[str, Any] | list[Any] | None
    timestamp: datetime

    @field_validator("timestamp", mode="before")
    @classmethod
    def return_utc_timestamp(cls, value: datetime) -> datetime:
        return ensure_utc(value)
