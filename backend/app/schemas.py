from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.dates import current_date, ensure_utc
from app.services.condition_fields import ConditionFieldError, normalize_condition
from app.states import StateGroup, normalize_state_code

StateCode = Annotated[
    str,
    BeforeValidator(normalize_state_code),
    Field(min_length=2, max_length=2),
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RootSetupStatusRead(BaseModel):
    setup_required: bool


class RootSetupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("name")
    @classmethod
    def strip_root_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class HumanLoginCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=20)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class OAuthClientRegistrationCreate(BaseModel):
    # Dynamic-registration clients may send optional RFC metadata that PolicyOS
    # does not need to persist.
    model_config = ConfigDict(extra="ignore")

    redirect_uris: list[str] = Field(min_length=1, max_length=10)
    client_name: str = Field(default="MCP client", min_length=1, max_length=200)
    token_endpoint_auth_method: Literal["none"] = "none"
    grant_types: list[Literal["authorization_code", "refresh_token"]] = Field(
        default_factory=lambda: ["authorization_code", "refresh_token"]
    )
    response_types: list[Literal["code"]] = Field(default_factory=lambda: ["code"])


class OAuthClientRegistrationRead(BaseModel):
    client_id: str
    client_name: str
    redirect_uris: list[str]
    token_endpoint_auth_method: Literal["none"] = "none"
    grant_types: list[str] = Field(
        default_factory=lambda: ["authorization_code", "refresh_token"]
    )
    response_types: list[str] = Field(default_factory=lambda: ["code"])


class OAuthAuthorizationRequestRead(BaseModel):
    client_id: str
    client_name: str
    redirect_uri: str
    scope: str
    state: str | None
    resource: str


class OAuthAuthorizationDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(min_length=1, max_length=200)
    redirect_uri: str = Field(min_length=1, max_length=1000)
    response_type: Literal["code"] = "code"
    code_challenge: str = Field(min_length=43, max_length=128)
    code_challenge_method: Literal["S256"] = "S256"
    scope: str = Field(default="policyos", max_length=500)
    state: str | None = Field(default=None, max_length=1000)
    resource: str | None = Field(default=None, max_length=1000)
    approve: bool


class OAuthAuthorizationDecisionRead(BaseModel):
    redirect_uri: str


class OAuthTokenRead(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str


class OAuthUserInfoRead(BaseModel):
    sub: str
    user_id: int
    client_id: str
    scopes: list[str]
    expires_at: int
    resource: str


class PasswordResetRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class PasswordResetRequestRead(BaseModel):
    message: str
    reset_token: str | None = None


class PasswordResetConfirmCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=12, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=20)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class MFASetupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)


class MFASetupRead(BaseModel):
    secret: str
    provisioning_uri: str


class MFAConfirmCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=20)


class MFAConfirmRead(BaseModel):
    recovery_codes: list[str]


class MFADisableCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=20)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class ReauthenticateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=20)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class AuthSessionRead(BaseModel):
    id: int
    current: bool
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    created_ip: str | None
    last_ip: str | None
    user_agent: str | None
    mfa_verified: bool


class SecurityEventRead(ORMModel):
    id: int
    event_type: str
    severity: Literal["info", "warning", "critical"]
    details: dict[str, Any]
    created_at: datetime
    acknowledged_at: datetime | None


class AccountSecurityRead(BaseModel):
    mfa_enabled: bool
    mfa_required: bool
    sessions: list[AuthSessionRead]
    events: list[SecurityEventRead]


class AccessReviewFindingRead(BaseModel):
    severity: Literal["info", "warning", "critical"]
    code: str
    subject_type: Literal["user", "role"]
    subject_id: int
    subject_name: str
    message: str


class AccessReviewRead(BaseModel):
    generated_at: datetime
    active_user_count: int
    role_count: int
    privileged_user_count: int
    privileged_users_without_mfa: int
    unused_role_count: int
    findings: list[AccessReviewFindingRead]


class PasswordChangeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class PermissionRead(BaseModel):
    name: str
    group: str
    label: str
    description: str


class RoleSummaryRead(ORMModel):
    id: int
    name: str


class RoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list)
    employee_scope: Literal["all", "reporting_tree", "self", "none"] = "none"
    assignment_field_scope: Literal["all", "selected", "none"] = "none"
    assignment_field_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_assignment_field_scope(self) -> RoleCreate:
        if self.assignment_field_scope == "selected" and not self.assignment_field_ids:
            raise ValueError(
                "Selected assignment fields must include at least one field"
            )
        if self.assignment_field_scope != "selected" and self.assignment_field_ids:
            raise ValueError("Assignment field IDs are only valid for selected scope")
        return self


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] | None = None
    employee_scope: Literal["all", "reporting_tree", "self", "none"] | None = None
    assignment_field_scope: Literal["all", "selected", "none"] | None = None
    assignment_field_ids: list[int] | None = None


class RoleRead(ORMModel):
    id: int
    name: str
    description: str | None
    employee_scope: Literal["all", "reporting_tree", "self", "none"]
    assignment_field_scope: Literal["all", "selected", "none"]
    assignment_field_ids: list[int]
    permissions: list[str]
    user_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class RoleDirectoryRead(BaseModel):
    id: int
    name: str
    description: str | None
    employee_scope: Literal["all", "reporting_tree", "self", "none"]
    assignment_field_scope: Literal["all", "selected", "none"]
    assignment_field_count: int = Field(ge=0)
    permission_count: int = Field(ge=0)
    permission_preview: list[str] = Field(default_factory=list)
    user_count: int = Field(ge=0)


class RoleCandidateRead(BaseModel):
    id: int
    name: str
    employee_scope: Literal["all", "reporting_tree", "self", "none"]
    assignment_field_scope: Literal["all", "selected", "none"]
    assignment_field_count: int = Field(ge=0)
    permission_count: int = Field(ge=0)
    user_count: int = Field(ge=0)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    temporary_password: str = Field(min_length=12, max_length=128)
    role_ids: list[int] = Field(min_length=1)
    employee_id: int | None = Field(default=None, gt=0)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "suspended", "disabled"] | None = None
    role_ids: list[int] | None = None
    employee_id: int | None = Field(default=None, gt=0)


class UserPasswordResetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temporary_password: str = Field(min_length=12, max_length=128)


class UserRead(ORMModel):
    id: int
    email: EmailStr
    name: str
    status: Literal["active", "suspended", "disabled"]
    is_root: bool
    password_change_required: bool
    mfa_enabled: bool
    employee_id: int | None
    employee_link_hidden: bool = False
    created_at: datetime
    last_login_at: datetime | None
    roles: list[RoleSummaryRead] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class EmployeeLinkSummaryRead(BaseModel):
    id: int
    name: str
    department: str


class EmployeeCandidateRead(EmployeeLinkSummaryRead):
    pass


class UserDirectoryRead(BaseModel):
    id: int
    email: EmailStr
    name: str
    status: Literal["active", "suspended", "disabled"]
    is_root: bool
    password_change_required: bool
    employee: EmployeeLinkSummaryRead | None
    employee_link_hidden: bool = False
    roles: list[RoleSummaryRead] = Field(default_factory=list)
    effective_permission_count: int = Field(ge=0)
    has_all_permissions: bool = False


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    state: StateCode
    department: str = Field(min_length=1, max_length=100)
    employee_type: str = Field(min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date = Field(default_factory=current_date)
    manager_id: int | None = Field(default=None, gt=0)


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    state: StateCode | None = None
    department: str | None = Field(default=None, min_length=1, max_length=100)
    employee_type: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    manager_id: int | None = Field(default=None, gt=0)


class EmployeeRead(EmployeeCreate, ORMModel):
    id: int
    state_label: str


class EmployeeManagerSummaryRead(ORMModel):
    id: int
    name: str


class EmployeeDetailRead(EmployeeRead):
    manager: EmployeeManagerSummaryRead | None


class StateRead(BaseModel):
    code: str = Field(min_length=2, max_length=2)
    name: str
    label: str
    group: StateGroup


class EmployeeReferenceDataRead(BaseModel):
    departments: list[str]
    employee_types: list[str]
    states: list[StateRead]


class EmployeeDirectoryRead(EmployeeRead):
    active_assignment_count: int = Field(ge=0)


class EmployeeManagerCandidateRead(BaseModel):
    id: int
    label: str


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class GroupRead(GroupCreate, ORMModel):
    id: int


class GroupDirectoryRead(GroupRead):
    member_count: int = Field(ge=0)
    policy_count: int = Field(ge=0)


class GroupMembershipUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    add_employee_ids: list[Annotated[int, Field(gt=0)]] = Field(
        default_factory=list,
        max_length=500,
    )
    remove_employee_ids: list[Annotated[int, Field(gt=0)]] = Field(
        default_factory=list,
        max_length=500,
    )

    @field_validator("add_employee_ids", "remove_employee_ids")
    @classmethod
    def require_unique_employee_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("Employee IDs must be unique")
        return value

    @model_validator(mode="after")
    def require_disjoint_membership_changes(self) -> GroupMembershipUpdate:
        if set(self.add_employee_ids) & set(self.remove_employee_ids):
            raise ValueError("An employee cannot be both added and removed")
        return self


class GroupPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    add_policy_ids: list[Annotated[int, Field(gt=0)]] = Field(
        default_factory=list,
        max_length=500,
    )
    remove_policy_ids: list[Annotated[int, Field(gt=0)]] = Field(
        default_factory=list,
        max_length=500,
    )

    @field_validator("add_policy_ids", "remove_policy_ids")
    @classmethod
    def require_unique_policy_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("Policy IDs must be unique")
        return value

    @model_validator(mode="after")
    def require_disjoint_policy_changes(self) -> GroupPolicyUpdate:
        if set(self.add_policy_ids) & set(self.remove_policy_ids):
            raise ValueError("A policy cannot be both added and removed")
        return self


class AssignmentFieldInputOptionRead(BaseModel):
    value: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=200)

    @field_validator("value", "label")
    @classmethod
    def strip_option_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class AssignmentFieldInputRead(BaseModel):
    type: Literal["text", "select"] = "text"
    options: list[AssignmentFieldInputOptionRead] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_options(self) -> AssignmentFieldInputRead:
        if self.type == "select" and not self.options:
            raise ValueError("Select assignment fields require at least one option")
        if self.type == "text" and self.options:
            raise ValueError("Text assignment fields cannot define options")
        values = [option.value.casefold() for option in self.options]
        if len(values) != len(set(values)):
            raise ValueError("Assignment field option values must be unique")
        return self


class AssignmentFieldDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cardinality: Literal["one", "many"]
    conflict_resolution: str = Field(default="priority", min_length=1, max_length=50)
    input: AssignmentFieldInputRead = Field(default_factory=AssignmentFieldInputRead)


class AssignmentFieldDefinitionRead(AssignmentFieldDefinitionCreate, ORMModel):
    id: int


class AssignmentFieldIdentityRead(ORMModel):
    id: int
    name: str


class AssignmentFieldScopeOptionRead(AssignmentFieldIdentityRead):
    cardinality: Literal["one", "many"]


class AssignmentFieldOverrideOptionRead(ORMModel):
    id: int
    name: str
    cardinality: Literal["one", "many"]
    input: AssignmentFieldInputRead


class AssignmentFieldDefinitionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: AssignmentFieldInputRead


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
        if (
            "assignment_field_definition_id" in self.model_fields_set
            and self.assignment_field_definition_id is None
        ):
            raise ValueError("assignment_field_definition_id cannot be null")
        if "value" in self.model_fields_set and self.value is None:
            raise ValueError("value cannot be null")
        return self


class EmployeeOverrideRead(ORMModel):
    id: int
    value: str
    assignment_field_definition: AssignmentFieldIdentityRead


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
            raise ValueError(
                "A condition group must contain a condition or child group"
            )
        return self


class PolicyVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int
    effective_from: date = Field(default_factory=current_date)
    effective_until: date | None = None
    created_by: str | None = Field(default=None, min_length=1, max_length=200)
    condition_group: ConditionGroupCreate
    values: list[PolicyValueCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def require_a_valid_effective_range(self) -> PolicyVersionCreate:
        if (
            self.effective_until is not None
            and self.effective_until < self.effective_from
        ):
            raise ValueError("effective_until cannot be before effective_from")
        return self


class PolicyCreate(PolicyVersionCreate):
    name: str = Field(min_length=1, max_length=200)
    status: Literal["draft", "active", "archived"] = "active"


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["draft", "active", "archived"] | None = None


class PolicyValueRead(PolicyValueCreate, ORMModel):
    pass


class ConditionRead(ORMModel):
    field: str
    operator: Literal["=", "<", "<=", ">", ">="]
    value: str
    display_value: str


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


class PolicyCapabilitiesRead(BaseModel):
    can_update: bool = False
    can_create_version: bool = False
    can_activate: bool = False
    can_archive: bool = False


class PolicyRead(ORMModel):
    id: int
    name: str
    status: Literal["draft", "active", "archived"]
    created_at: datetime
    created_by: str | None = None
    versions: list[PolicyVersionRead]
    capabilities: PolicyCapabilitiesRead = Field(default_factory=PolicyCapabilitiesRead)


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


class AssignmentConditionEvidenceRead(BaseModel):
    field: str
    operator: str
    expected: Any
    actual: Any
    expected_label: str | None = None
    actual_label: str | None = None


class AssignmentClauseEvidenceRead(BaseModel):
    conditions: list[AssignmentConditionEvidenceRead] = Field(default_factory=list)


class AssignmentOriginSummaryRead(BaseModel):
    type: Literal["condition_match", "group", "persisted_policy_link"]
    group_name: str | None = None
    matched_clauses: list[AssignmentClauseEvidenceRead] = Field(default_factory=list)


class AssignmentPolicySummaryRead(BaseModel):
    name: str


class AssignmentOverrideSummaryRead(BaseModel):
    value: str


class ReplacedPolicyAssignmentRead(BaseModel):
    value: str
    policy_name: str | None = None


class AssignmentSelectionSummaryRead(BaseModel):
    priority: int | None = None
    replaced_policy_assignments: list[ReplacedPolicyAssignmentRead] = Field(
        default_factory=list
    )


class AssignmentExplanationSummaryRead(BaseModel):
    reason: Literal["policy", "manual_override"]
    policy: AssignmentPolicySummaryRead | None = None
    origins: list[AssignmentOriginSummaryRead] = Field(default_factory=list)
    selection: AssignmentSelectionSummaryRead | None = None
    override: AssignmentOverrideSummaryRead | None = None


class CurrentAssignmentRead(BaseModel):
    id: int
    value: str
    source_policy_version_id: int | None
    source_override_id: int | None
    explanation: AssignmentExplanationSummaryRead
    assignment_field_definition: AssignmentFieldIdentityRead


class AssignmentHistoryRead(BaseModel):
    id: int
    value: str
    source_type: Literal["policy", "override"]
    effective_from: datetime
    effective_until: datetime | None
    assignment_field_definition: AssignmentFieldIdentityRead

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


class ImpactSummaryConflictRead(BaseModel):
    employee_id: int
    code: str
    message: str
    assignment_field_definition_id: int | None = None
    assignment_field_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssignmentFieldSummaryRead(BaseModel):
    assignment_field_definition: AssignmentFieldDefinitionRead
    assigned_employee_count: int
    assignment_count: int
    policy_assignment_count: int
    override_assignment_count: int
    distinct_value_count: int
    value_samples: list[str]
    values_truncated: bool


class AssignmentSummaryRead(BaseModel):
    scope: Literal["population", "employee"]
    employee_id: int | None = None
    evaluation_date: date
    mode: Literal[
        "recorded_history",
        "current_persisted",
        "calculated_future",
    ]
    complete: bool
    employee_count: int
    employees_with_assignments: int
    employees_without_assignments: int
    assignment_count: int
    policy_assignment_count: int
    override_assignment_count: int
    field_count: int
    fields: list[AssignmentFieldSummaryRead]
    conflicted_employee_count: int
    conflicts: list[ImpactSummaryConflictRead]
    conflicts_truncated: bool


class PolicyFieldImpactSummaryRead(BaseModel):
    assignment_field_definition: AssignmentFieldDefinitionRead
    configured_value_count: int
    configured_value_samples: list[str]
    configured_values_truncated: bool
    selected_employee_count: int
    selected_assignment_count: int
    suppressed_by_override_employee_count: int
    suppressed_by_override_assignment_count: int


class PolicyImpactSummaryRead(BaseModel):
    policy_id: int
    policy_name: str
    policy_status: Literal["draft", "active", "archived"]
    evaluation_date: date
    mode: Literal["current", "calculated_future"]
    calculation_basis: Literal["live_resolution_current_employee_facts"]
    complete: bool
    effective: bool
    effective_policy_version_id: int | None
    effective_version_number: int | None
    total_employee_count: int
    matched_employee_count: int
    direct_match_employee_count: int
    group_match_employee_count: int
    direct_and_group_match_employee_count: int
    selected_employee_count: int
    selected_assignment_count: int
    matched_without_selected_assignment_count: int
    suppressed_by_override_employee_count: int
    suppressed_by_override_assignment_count: int
    fields: list[PolicyFieldImpactSummaryRead]
    conflicted_employee_count: int
    conflicts: list[ImpactSummaryConflictRead]
    conflicts_truncated: bool


class AuditLogRead(ORMModel):
    id: int
    actor: str
    entity_type: str
    entity_id: int
    action: str
    before: dict[str, Any] | list[Any] | None
    after: dict[str, Any] | list[Any] | None
    timestamp: datetime
    entity_label: str = ""

    @field_validator("timestamp", mode="before")
    @classmethod
    def return_utc_timestamp(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class AuditLogFacetsRead(BaseModel):
    entity_types: list[str]
    actions: list[str]


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
        "not_found",
        "service",
    ]
    code: str
    message: str
    issues: list[APIErrorIssueRead]


class APIErrorResponseRead(BaseModel):
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


class PolicyCreateChangePreview(_ChangePreviewBase):
    type: Literal["policy_create"]
    policy: PolicyCreate


class PolicyVersionCreateChangePreview(_ChangePreviewBase):
    type: Literal["policy_version_create"]
    policy_id: int = Field(gt=0)
    version: PolicyVersionCreate


class PolicyStatusChangePreview(_ChangePreviewBase):
    type: Literal["policy_status_change"]
    policy_id: int = Field(gt=0)
    status: Literal["draft", "active", "archived"]


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


ChangePreviewCreate = Annotated[
    EmployeeCreateChangePreview
    | EmployeeUpdateChangePreview
    | PolicyCreateChangePreview
    | PolicyVersionCreateChangePreview
    | PolicyStatusChangePreview
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


class PolicyPreviewEmployeeRead(BaseModel):
    employee_id: int
    employee_name: str
    department: str


class PolicyPreviewAssignmentRead(BaseModel):
    assignment_field_definition_id: int
    assignment_field_name: str
    value: str


class PolicyAssignmentPreviewRead(BaseModel):
    """Frontend-facing impact summary for a proposed policy or policy version."""

    type: Literal["policy_create", "policy_version_create"]
    affected_employees: list[PolicyPreviewEmployeeRead]
    assignments_per_match: list[PolicyPreviewAssignmentRead]
    conflict_message: str | None = None


class ChangePreviewConflictRead(BaseModel):
    code: str
    message: str
    path: list[str | int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmployeeAssignmentPreviewRead(BaseModel):
    """Assignment consequences of creating or updating one employee."""

    type: Literal["employee_create", "employee_update"]
    valid: bool
    before_assignments: list[AssignmentPreviewRead]
    after_assignments: list[AssignmentPreviewRead]
    conflicts: list[ChangePreviewConflictRead]
    warnings: list[str]


class ChangePreviewRead(BaseModel):
    type: Literal[
        "policy_create",
        "policy_version_create",
        "policy_status_change",
        "group_membership_change",
        "employee_override_change",
    ]
    valid: bool
    affected_employee_count: int
    changes: list[EmployeeAssignmentPreviewChangeRead]
    conflicts: list[ChangePreviewConflictRead]
    warnings: list[str]


class NonPolicyChangePreviewRead(ChangePreviewRead):
    type: Literal[
        "policy_status_change",
        "group_membership_change",
        "employee_override_change",
    ]


ChangePreviewResponse = Annotated[
    EmployeeAssignmentPreviewRead
    | PolicyAssignmentPreviewRead
    | NonPolicyChangePreviewRead,
    Field(discriminator="type"),
]
