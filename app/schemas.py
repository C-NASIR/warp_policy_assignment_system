from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

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


class AssignmentFieldDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cardinality: Literal["one", "many"]
    conflict_resolution: str = Field(default="priority", min_length=1, max_length=50)


class AssignmentFieldDefinitionRead(AssignmentFieldDefinitionCreate, ORMModel):
    id: int


class ConditionFieldDependencyRead(ORMModel):
    id: int
    dependency_type: Literal["column", "relationship", "time"]
    dependency_key: str
    source_table: str | None
    source_column: str | None
    role: str
    impact_resolver_key: str


class ConditionFieldInputOptionRead(BaseModel):
    value: str
    label: str


class ConditionFieldInputRead(BaseModel):
    type: Literal["text", "date", "number", "select", "duration", "resource"]
    allows_null: bool
    placeholder: str | None
    options: list[ConditionFieldInputOptionRead]
    reference_resource: str | None
    minimum: int | None


class ConditionFieldDefinitionRead(ORMModel):
    id: int
    key: str
    label: str
    description: str
    field_type: Literal["static", "derived"]
    data_type: str
    allowed_operators: list[Literal["=", "<", "<=", ">", ">="]]
    input: ConditionFieldInputRead
    resolver_key: str | None
    source_table: str | None
    source_column: str | None
    active: bool
    dependencies: list[ConditionFieldDependencyRead]


class EmployeeOverrideCreate(BaseModel):
    assignment_field_definition_id: int
    value: str = Field(min_length=1, max_length=500)


class EmployeeOverrideUpdate(BaseModel):
    assignment_field_definition_id: int | None = None
    value: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_a_change(self) -> EmployeeOverrideUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one override field must be provided")
        if "assignment_field_definition_id" in self.model_fields_set and self.assignment_field_definition_id is None:
            raise ValueError("assignment_field_definition_id cannot be null")
        if "value" in self.model_fields_set and self.value is None:
            raise ValueError("value cannot be null")
        return self


class EmployeeOverrideRead(ORMModel):
    id: int
    employee_id: int
    assignment_field_definition_id: int
    value: str
    retired_at: datetime | None
    assignment_field_definition: AssignmentFieldDefinitionRead


class PolicyValueCreate(BaseModel):
    assignment_field_definition_id: int
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


class ConditionRead(ORMModel):
    field: str
    operator: Literal["=", "<", "<=", ">", ">="]
    value: str


class ConditionGroupRead(ORMModel):
    logical_operator: Literal["and", "or"]
    conditions: list[ConditionRead]
    child_groups: list[ConditionGroupRead]


class PolicyVersionRead(ORMModel):
    id: int
    policy_id: int
    version_number: int
    priority: int
    effective_from: date
    effective_until: date | None
    created_at: datetime
    created_by: str | None
    condition_group: ConditionGroupRead
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
    assignment_field_definition_id: int
    value: str
    source_policy_version_id: int | None
    source_override_id: int | None
    explanation: dict[str, Any]
    effective_from: datetime
    effective_until: datetime | None
    assignment_field_definition: AssignmentFieldDefinitionRead

    @field_validator("effective_from", "effective_until", mode="before")
    @classmethod
    def return_utc_timestamps(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class AssignmentQueryCreate(BaseModel):
    employee_ids: list[int] = Field(min_length=1, max_length=1000)
    evaluation_date: date

    @field_validator("employee_ids")
    @classmethod
    def require_positive_employee_ids(cls, value: list[int]) -> list[int]:
        if any(employee_id <= 0 for employee_id in value):
            raise ValueError("employee_ids must contain only positive integers")
        return value


class AssignmentQueryValueRead(ORMModel):
    persisted_assignment_id: int | None
    assignment_field_definition: AssignmentFieldDefinitionRead
    value: str
    source_policy_version_id: int | None
    source_override_id: int | None
    explanation: dict[str, Any]
    effective_from: datetime | None
    effective_until: datetime | None

    @field_validator("effective_from", "effective_until", mode="before")
    @classmethod
    def return_utc_timestamps(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class EmployeeAssignmentQueryRead(ORMModel):
    employee_id: int
    evaluation_date: date
    mode: Literal[
        "recorded_history",
        "current_persisted",
        "calculated_future",
    ]
    assignments: list[AssignmentQueryValueRead]


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


class OperationScopeRead(BaseModel):
    name: str
    description: str


class APICredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(min_length=1)
    expires_at: datetime | None = None

    @field_validator("name", "subject")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("scopes")
    @classmethod
    def normalize_scopes(cls, value: list[str]) -> list[str]:
        normalized = [scope.strip() for scope in value]
        if any(not scope for scope in normalized):
            raise ValueError("scope names must not be blank")
        return normalized

    @field_validator("expires_at", mode="before")
    @classmethod
    def normalize_expiry(cls, value: datetime | str | None) -> datetime | None:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return ensure_utc(value) if value is not None else None


class APICredentialRead(ORMModel):
    id: int
    name: str
    subject: str
    token_prefix: str
    scopes: list[str]
    created_by: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None

    @field_validator("created_at", "expires_at", "revoked_at", mode="before")
    @classmethod
    def normalize_timestamps(
        cls,
        value: datetime | str | None,
    ) -> datetime | None:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return ensure_utc(value) if value is not None else None


class APICredentialCreatedRead(APICredentialRead):
    token: str


class APIErrorIssueRead(BaseModel):
    code: str
    message: str
    path: list[str | int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class APIErrorRead(BaseModel):
    category: Literal[
        "validation",
        "conflict",
        "authentication",
        "authorization",
    ]
    code: str
    message: str
    issues: list[APIErrorIssueRead]


class APIErrorResponseRead(BaseModel):
    # Kept during the transition from FastAPI's legacy error response shape.
    detail: Any
    error: APIErrorRead


class _ChangePreviewBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmployeeCreateChangePreview(_ChangePreviewBase):
    type: Literal["employee_create"]
    employee: EmployeeCreate


class EmployeeUpdateChangePreview(_ChangePreviewBase):
    type: Literal["employee_update"]
    employee_id: int = Field(gt=0)
    changes: EmployeeUpdate


class PolicyVersionCreateChangePreview(_ChangePreviewBase):
    type: Literal["policy_version_create"]
    policy_id: int = Field(gt=0)
    version: PolicyVersionCreate


class GroupMembershipChangePreview(_ChangePreviewBase):
    type: Literal["group_membership_change"]
    action: Literal["add", "remove"]
    group_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)


class EmployeeOverrideChangePreview(_ChangePreviewBase):
    type: Literal["employee_override_change"]
    action: Literal["create", "update", "delete"]
    employee_id: int = Field(gt=0)
    override_id: int | None = Field(default=None, gt=0)
    assignment_field_definition_id: int | None = Field(default=None, gt=0)
    value: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_fields_for_override_action(self) -> EmployeeOverrideChangePreview:
        if self.action == "create":
            if self.override_id is not None:
                raise ValueError("override_id is not accepted when creating an override")
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


ChangePreviewCreate = Annotated[
    EmployeeCreateChangePreview
    | EmployeeUpdateChangePreview
    | PolicyVersionCreateChangePreview
    | GroupMembershipChangePreview
    | EmployeeOverrideChangePreview,
    Field(discriminator="type"),
]


class AssignmentPreviewRead(BaseModel):
    assignment_field_definition_id: int
    assignment_field_name: str
    value: str
    source_type: Literal["policy_version", "override"]
    source_id: int | None
    source_is_proposed: bool
    explanation: dict[str, Any]


class AssignmentFieldPreviewChangeRead(BaseModel):
    assignment_field_definition_id: int
    assignment_field_name: str
    before: list[AssignmentPreviewRead]
    after: list[AssignmentPreviewRead]


class EmployeeAssignmentPreviewChangeRead(BaseModel):
    employee_id: int | None
    employee_name: str
    before: list[AssignmentPreviewRead]
    after: list[AssignmentPreviewRead]
    added: list[AssignmentPreviewRead]
    removed: list[AssignmentPreviewRead]
    changed: list[AssignmentFieldPreviewChangeRead]


class ChangePreviewConflictRead(BaseModel):
    code: str
    message: str
    path: list[str | int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChangeApprovalRead(BaseModel):
    approval_id: str
    token: str
    issued_at: datetime
    expires_at: datetime
    change_digest: str
    precondition_digest: str
    preview_digest: str

    @field_validator("issued_at", "expires_at", mode="before")
    @classmethod
    def return_utc_timestamps(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ChangePreviewRead(BaseModel):
    change_type: str
    valid: bool
    affected_employee_count: int
    changes: list[EmployeeAssignmentPreviewChangeRead]
    conflicts: list[ChangePreviewConflictRead]
    warnings: list[str]
    approval: ChangeApprovalRead | None = None


class ApprovedChangeExecutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_token: str = Field(min_length=1, max_length=4000)
    change: ChangePreviewCreate


class ApprovedChangeExecutionRead(BaseModel):
    approval_id: str
    status: Literal["executed"]
    replayed: bool
    change_type: str
    executed_at: datetime
    executed_by: str
    affected_employee_count: int
    changes: list[EmployeeAssignmentPreviewChangeRead]
    resources: dict[str, int]

    @field_validator("executed_at", mode="before")
    @classmethod
    def return_utc_timestamp(cls, value: datetime | str) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return ensure_utc(value)
