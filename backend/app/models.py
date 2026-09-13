from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.dates import current_date, current_datetime
from app.states import STATE_CODES, state_label


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_actor", "actor"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int] = mapped_column()
    action: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )


class APICredential(Base):
    __tablename__ = "api_credentials"
    __table_args__ = (
        Index("ix_api_credentials_subject", "subject"),
        Index(
            "ix_api_credentials_lifecycle",
            "revoked_at",
            "expires_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    subject: Mapped[str] = mapped_column(String(200))
    token_prefix: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint(
            "employee_scope IN ('all', 'reporting_tree', 'self', 'none')",
            name="ck_role_employee_scope",
        ),
        CheckConstraint(
            "assignment_field_scope IN ('all', 'selected', 'none')",
            name="ck_role_assignment_field_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    employee_scope: Mapped[Literal["all", "reporting_tree", "self", "none"]] = (
        mapped_column(String(30), default="none", server_default="none")
    )
    assignment_field_scope: Mapped[Literal["all", "selected", "none"]] = mapped_column(
        String(20), default="none", server_default="none"
    )
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
        onupdate=current_datetime,
    )
    role_permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    assignment_field_links: Mapped[list[RoleAssignmentFieldScope]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    users: Mapped[list[User]] = relationship(
        secondary="user_roles",
        back_populates="roles",
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission: Mapped[str] = mapped_column(String(100), primary_key=True)
    role: Mapped[Role] = relationship(back_populates="role_permissions")


class RoleAssignmentFieldScope(Base):
    __tablename__ = "role_assignment_field_scopes"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assignment_field_definition_id: Mapped[int] = mapped_column(
        ForeignKey("assignment_field_definitions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[Role] = relationship(back_populates="assignment_field_links")
    assignment_field_definition: Mapped[AssignmentFieldDefinition] = relationship()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'disabled')",
            name="ck_user_status",
        ),
        Index("ix_users_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(500))
    status: Mapped[Literal["active", "suspended", "disabled"]] = mapped_column(
        String(20),
        default="active",
        server_default="active",
    )
    is_root: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    password_change_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    mfa_secret_ciphertext: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    mfa_recovery_code_hashes: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        server_default="[]",
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
        onupdate=current_datetime,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    security_events: Mapped[list[SecurityEvent]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    roles: Mapped[list[Role]] = relationship(
        secondary="user_roles",
        back_populates="users",
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_lifecycle", "user_id", "revoked_at", "expires_at"),
        Index("ix_auth_sessions_expiry", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reauthenticated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    mfa_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pending_mfa_secret_ciphertext: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    user: Mapped[User] = relationship(back_populates="sessions")


class LoginThrottle(Base):
    __tablename__ = "login_throttles"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failed_count: Mapped[int] = mapped_column(default=0, server_default="0")
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_tokens_user", "user_id", "created_at"),
        Index("ix_password_reset_tokens_expiry", "expires_at", "used_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    requested_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="ck_security_event_severity",
        ),
        Index("ix_security_events_user_created", "user_id", "created_at"),
        Index("ix_security_events_severity", "severity", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[Literal["info", "warning", "critical"]] = mapped_column(String(20))
    details: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    user: Mapped[User] = relationship(back_populates="security_events")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class ApprovedChangeExecution(Base):
    __tablename__ = "approved_change_executions"

    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    change_type: Mapped[str] = mapped_column(String(100))
    change_digest: Mapped[str] = mapped_column(String(64))
    precondition_digest: Mapped[str] = mapped_column(String(64))
    preview_digest: Mapped[str] = mapped_column(String(64))
    executed_by: Mapped[str] = mapped_column(String(200))
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    response: Mapped[dict] = mapped_column(JSON)


class ChangeApprovalRequest(Base):
    __tablename__ = "change_approval_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'executed', 'expired')",
            name="ck_change_approval_request_status",
        ),
        Index("ix_change_approval_requests_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[
        Literal["pending", "approved", "rejected", "executed", "expired"]
    ] = mapped_column(String(20), default="pending", server_default="pending")
    change_type: Mapped[str] = mapped_column(String(100))
    change: Mapped[dict] = mapped_column(JSON)
    preview: Mapped[dict] = mapped_column(JSON)
    change_digest: Mapped[str] = mapped_column(String(64))
    precondition_digest: Mapped[str] = mapped_column(String(64))
    preview_digest: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(200))
    requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejected_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approval_token: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ScheduledReconciliation(Base):
    __tablename__ = "scheduled_reconciliations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processed', 'cancelled')",
            name="ck_scheduled_reconciliation_status",
        ),
        CheckConstraint(
            "(status = 'processed' AND processed_at IS NOT NULL) OR "
            "(status IN ('pending', 'cancelled') AND processed_at IS NULL)",
            name="ck_scheduled_reconciliation_processed_at",
        ),
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "trigger_type",
            "scheduled_at",
            name="uq_scheduled_reconciliation_event",
        ),
        Index(
            "ix_scheduled_reconciliations_due",
            "status",
            "scheduled_at",
        ),
        Index(
            "ix_scheduled_reconciliations_entity",
            "entity_type",
            "entity_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int] = mapped_column()
    trigger_type: Mapped[str] = mapped_column(String(100))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[Literal["pending", "processed", "cancelled"]] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class EmployeePolicy(Base):
    __tablename__ = "employee_policies"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    )
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        primary_key=True,
    )


class EmployeeGroupMembership(Base):
    __tablename__ = "employee_group_memberships"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    )


class GroupPolicy(Base):
    __tablename__ = "group_policies"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        Index(
            "ix_employees_population_filters",
            "state_code",
            "department",
            "employee_type",
        ),
        Index("ix_employees_start_date", "start_date"),
        CheckConstraint(
            f"state_code IN ({', '.join(repr(code) for code in sorted(STATE_CODES))})",
            name="ck_employees_state_code",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column("state_code", String(2))
    department: Mapped[str] = mapped_column(String(100))
    employee_type: Mapped[str] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date] = mapped_column(
        Date,
        default=current_date,
        server_default=func.current_date(),
    )
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    manager: Mapped[Employee | None] = relationship(
        back_populates="direct_reports",
        foreign_keys=[manager_id],
        remote_side=[id],
    )
    direct_reports: Mapped[list[Employee]] = relationship(
        back_populates="manager",
        foreign_keys=[manager_id],
        passive_deletes=True,
    )

    @property
    def state_label(self) -> str:
        return state_label(self.state)

    policies: Mapped[list[Policy]] = relationship(
        secondary="employee_policies", back_populates="employees"
    )
    groups: Mapped[list[Group]] = relationship(
        secondary="employee_group_memberships",
        back_populates="employees",
    )
    overrides: Mapped[list[EmployeeOverride]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list[EmployeeAssignment]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    employees: Mapped[list[Employee]] = relationship(
        secondary="employee_group_memberships",
        back_populates="groups",
    )
    policies: Mapped[list[Policy]] = relationship(
        secondary="group_policies",
        back_populates="groups",
    )


class AssignmentFieldDefinition(Base):
    __tablename__ = "assignment_field_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    cardinality: Mapped[Literal["one", "many"]] = mapped_column(String(10))
    conflict_resolution: Mapped[str] = mapped_column(String(50), default="priority")
    input: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {"type": "text", "options": []},
        server_default='{"type":"text","options":[]}',
    )
    overrides: Mapped[list[EmployeeOverride]] = relationship(
        back_populates="assignment_field_definition"
    )


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (Index("ix_policies_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[Literal["draft", "active", "archived"]] = mapped_column(
        String(20), default="active"
    )
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        default=datetime.now,
        server_default=func.now(),
    )
    employees: Mapped[list[Employee]] = relationship(
        secondary="employee_policies", back_populates="policies"
    )
    groups: Mapped[list[Group]] = relationship(
        secondary="group_policies", back_populates="policies"
    )
    versions: Mapped[list[PolicyVersion]] = relationship(
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="PolicyVersion.version_number",
    )


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "version_number"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="ck_policy_version_valid_effective_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        index=True,
    )
    version_number: Mapped[int]
    priority: Mapped[int]
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        default=datetime.now,
        server_default=func.now(),
    )
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    policy: Mapped[Policy] = relationship(back_populates="versions")
    values: Mapped[list[PolicyFieldValue]] = relationship(
        back_populates="policy_version",
        cascade="all, delete-orphan",
    )
    condition_groups: Mapped[list[ConditionGroup]] = relationship(
        back_populates="policy_version",
        cascade="all, delete-orphan",
        order_by="ConditionGroup.id",
    )
    compiled_clauses: Mapped[list[CompiledPolicyClause]] = relationship(
        back_populates="policy_version",
        cascade="all, delete-orphan",
    )

    @property
    def condition_group(self) -> ConditionGroup:
        """Return the canonical root condition group for API serialization."""
        roots = [
            group for group in self.condition_groups if group.parent_group_id is None
        ]
        if len(roots) != 1:
            raise ValueError(
                f"PolicyVersion {self.id} must have exactly one root condition group"
            )
        return roots[0]


class ConditionFieldDefinition(Base):
    __tablename__ = "condition_field_definitions"
    __table_args__ = (
        CheckConstraint(
            "field_type IN ('static', 'derived')",
            name="ck_condition_field_definition_type",
        ),
        CheckConstraint(
            "(field_type = 'static' AND source_table IS NOT NULL "
            "AND source_column IS NOT NULL) OR "
            "(field_type = 'derived' AND resolver_key IS NOT NULL)",
            name="ck_condition_field_definition_source",
        ),
        Index(
            "ix_condition_field_definitions_catalog_filters",
            "active",
            "field_type",
            "data_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(500))
    field_type: Mapped[Literal["static", "derived"]] = mapped_column(String(20))
    data_type: Mapped[str] = mapped_column(String(50))
    allowed_operators: Mapped[list[str]] = mapped_column(JSON)
    input: Mapped[dict] = mapped_column(JSON)
    resolver_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_table: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_column: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    dependencies: Mapped[list[ConditionFieldDependency]] = relationship(
        back_populates="condition_field_definition",
        cascade="all, delete-orphan",
    )


class ConditionFieldDependency(Base):
    __tablename__ = "condition_field_dependencies"
    __table_args__ = (
        CheckConstraint(
            "dependency_type IN ('column', 'relationship', 'time')",
            name="ck_condition_field_dependency_type",
        ),
        UniqueConstraint(
            "condition_field_definition_id",
            "dependency_key",
            "role",
            name="uq_condition_field_dependency",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    condition_field_definition_id: Mapped[int] = mapped_column(
        ForeignKey("condition_field_definitions.id", ondelete="CASCADE"),
        index=True,
    )
    dependency_type: Mapped[Literal["column", "relationship", "time"]] = mapped_column(
        String(20)
    )
    dependency_key: Mapped[str] = mapped_column(String(200))
    source_table: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_column: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(
        String(100), default="value", server_default="value"
    )
    impact_resolver_key: Mapped[str] = mapped_column(String(200))
    condition_field_definition: Mapped[ConditionFieldDefinition] = relationship(
        back_populates="dependencies"
    )


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    condition_field_definition_id: Mapped[int] = mapped_column(
        ForeignKey("condition_field_definitions.id")
    )
    operator: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500))
    condition_field_definition: Mapped[ConditionFieldDefinition] = relationship()
    group_links: Mapped[list[ConditionGroupCondition]] = relationship(
        back_populates="condition",
        cascade="all, delete-orphan",
    )

    @property
    def field(self) -> str:
        return self.condition_field_definition.key

    @property
    def display_value(self) -> str:
        return state_label(self.value) if self.field == "state" else self.value


class ConditionGroup(Base):
    __tablename__ = "condition_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE")
    )
    parent_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("condition_groups.id", ondelete="CASCADE"),
        nullable=True,
    )
    logical_operator: Mapped[Literal["and", "or"]] = mapped_column(String(10))
    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="condition_groups"
    )
    parent_group: Mapped[ConditionGroup | None] = relationship(
        back_populates="child_groups",
        remote_side="ConditionGroup.id",
    )
    child_groups: Mapped[list[ConditionGroup]] = relationship(
        back_populates="parent_group",
        cascade="all, delete-orphan",
        single_parent=True,
        order_by="ConditionGroup.id",
    )
    condition_links: Mapped[list[ConditionGroupCondition]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="ConditionGroupCondition.condition_id",
    )

    @property
    def conditions(self) -> list[Condition]:
        """Expose canonical conditions without leaking association rows."""
        return [link.condition for link in self.condition_links]


class ConditionGroupCondition(Base):
    __tablename__ = "condition_group_conditions"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("condition_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    condition_id: Mapped[int] = mapped_column(
        ForeignKey("conditions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group: Mapped[ConditionGroup] = relationship(back_populates="condition_links")
    condition: Mapped[Condition] = relationship(back_populates="group_links")


class CompiledPolicyClause(Base):
    __tablename__ = "compiled_policy_clauses"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        index=True,
    )
    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="compiled_clauses"
    )
    conditions: Mapped[list[CompiledPolicyCondition]] = relationship(
        back_populates="clause",
        cascade="all, delete-orphan",
    )


class CompiledPolicyCondition(Base):
    __tablename__ = "compiled_policy_conditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    clause_id: Mapped[int] = mapped_column(
        ForeignKey("compiled_policy_clauses.id", ondelete="CASCADE"),
        index=True,
    )
    condition_field_definition_id: Mapped[int] = mapped_column(
        ForeignKey("condition_field_definitions.id")
    )
    operator: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500))
    clause: Mapped[CompiledPolicyClause] = relationship(back_populates="conditions")
    condition_field_definition: Mapped[ConditionFieldDefinition] = relationship()

    @property
    def field(self) -> str:
        return self.condition_field_definition.key


class PolicyFieldValue(Base):
    __tablename__ = "policy_field_values"

    policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assignment_field_definition_id: Mapped[int] = mapped_column(
        ForeignKey("assignment_field_definitions.id"),
        primary_key=True,
    )
    value: Mapped[str] = mapped_column(String(500), primary_key=True)
    policy_version: Mapped[PolicyVersion] = relationship(back_populates="values")
    assignment_field_definition: Mapped[AssignmentFieldDefinition] = relationship()


class EmployeeOverride(Base):
    __tablename__ = "employee_overrides"
    __table_args__ = (
        Index(
            "ix_employee_overrides_employee_retired",
            "employee_id",
            "retired_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE")
    )
    assignment_field_definition_id: Mapped[int] = mapped_column(
        ForeignKey("assignment_field_definitions.id")
    )
    value: Mapped[str] = mapped_column(String(500))
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    employee: Mapped[Employee] = relationship(back_populates="overrides")
    assignment_field_definition: Mapped[AssignmentFieldDefinition] = relationship(
        back_populates="overrides"
    )


class EmployeeAssignment(Base):
    __tablename__ = "employee_assignments"
    __table_args__ = (
        CheckConstraint(
            "(source_policy_version_id IS NOT NULL AND source_override_id IS NULL) OR "
            "(source_policy_version_id IS NULL AND source_override_id IS NOT NULL)",
            name="ck_employee_assignment_exactly_one_source",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="ck_employee_assignment_valid_effective_range",
        ),
        Index(
            "ix_employee_assignments_employee_current",
            "employee_id",
            "effective_until",
        ),
        Index(
            "ix_employee_assignments_employee_assignment_field_start",
            "employee_id",
            "assignment_field_definition_id",
            "effective_from",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE")
    )
    assignment_field_definition_id: Mapped[int] = mapped_column(
        ForeignKey("assignment_field_definitions.id")
    )
    value: Mapped[str] = mapped_column(String(500))
    source_policy_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("policy_versions.id"),
        nullable=True,
    )
    source_override_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "employee_overrides.id",
            name="fk_employee_assignments_source_override_id",
        ),
        nullable=True,
    )
    explanation: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        server_default="{}",
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    employee: Mapped[Employee] = relationship(back_populates="assignments")
    assignment_field_definition: Mapped[AssignmentFieldDefinition] = relationship()
    source_policy_version: Mapped[PolicyVersion | None] = relationship()
    source_override: Mapped[EmployeeOverride | None] = relationship()
