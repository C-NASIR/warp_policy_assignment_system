from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    state: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=100)
    employee_type: str = Field(min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date = Field(default_factory=date.today)
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


class PolicyValueCreate(BaseModel):
    field_definition_id: int
    value: str = Field(min_length=1, max_length=500)


class ConditionCreate(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    operator: Literal["=", "<", "<="]
    value: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_a_typed_fact_value(self) -> ConditionCreate:
        if self.field == "start_date":
            try:
                date.fromisoformat(self.value)
            except ValueError as exc:
                raise ValueError("start_date condition values must be ISO dates (YYYY-MM-DD)") from exc
        elif self.field == "manager_id":
            try:
                manager_id = int(self.value)
            except ValueError as exc:
                raise ValueError("manager_id condition values must be positive integers") from exc
            if manager_id <= 0:
                raise ValueError("manager_id condition values must be positive integers")
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


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    priority: int
    condition_group: ConditionGroupCreate
    values: list[PolicyValueCreate] = Field(default_factory=list)


class PolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    priority: int | None = None
    condition_group: ConditionGroupCreate | None = None
    values: list[PolicyValueCreate] | None = None


class PolicyValueRead(PolicyValueCreate, ORMModel):
    pass


class PolicyRead(ORMModel):
    id: int
    name: str
    priority: int
    values: list[PolicyValueRead]


class AssignmentRead(ORMModel):
    id: int
    employee_id: int
    field_definition_id: int
    value: str
    source_policy_id: int
    field_definition: FieldDefinitionRead
