from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database import Base
from app.dates import current_date, current_datetime


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

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(100))
    department: Mapped[str] = mapped_column(String(100))
    employee_type: Mapped[str] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date] = mapped_column(
        Date,
        default=current_date,
        server_default=func.current_date(),
    )
    manager_id: Mapped[int | None] = mapped_column(nullable=True)
    policies: Mapped[list[Policy]] = relationship(secondary="employee_policies", back_populates="employees")
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


class FieldDefinition(Base):
    __tablename__ = "field_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    field: Mapped[str] = mapped_column(String(100), unique=True)
    # ``name`` keeps the current API backwards compatible while the persisted
    # field follows the domain vocabulary.
    name = synonym("field")
    cardinality: Mapped[Literal["one", "many"]] = mapped_column(String(10))
    conflict_resolution: Mapped[str] = mapped_column(String(50), default="priority")
    overrides: Mapped[list[EmployeeOverride]] = relationship(back_populates="field_definition")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[Literal["active", "archived"]] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        default=datetime.now,
        server_default=func.now(),
    )
    employees: Mapped[list[Employee]] = relationship(secondary="employee_policies", back_populates="policies")
    groups: Mapped[list[Group]] = relationship(secondary="group_policies", back_populates="policies")
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
    )
    compiled_clauses: Mapped[list[CompiledPolicyClause]] = relationship(
        back_populates="policy_version",
        cascade="all, delete-orphan",
    )


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    field: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500))
    group_links: Mapped[list[ConditionGroupCondition]] = relationship(
        back_populates="condition",
        cascade="all, delete-orphan",
    )


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
    policy_version: Mapped[PolicyVersion] = relationship(back_populates="condition_groups")
    parent_group: Mapped[ConditionGroup | None] = relationship(
        back_populates="child_groups",
        remote_side="ConditionGroup.id",
    )
    child_groups: Mapped[list[ConditionGroup]] = relationship(
        back_populates="parent_group",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    condition_links: Mapped[list[ConditionGroupCondition]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


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
    policy_version: Mapped[PolicyVersion] = relationship(back_populates="compiled_clauses")
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
    field: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500))
    clause: Mapped[CompiledPolicyClause] = relationship(back_populates="conditions")


class PolicyFieldValue(Base):
    __tablename__ = "policy_field_values"

    policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    field_definition_id: Mapped[int] = mapped_column(ForeignKey("field_definitions.id"), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), primary_key=True)
    policy_version: Mapped[PolicyVersion] = relationship(back_populates="values")
    field_definition: Mapped[FieldDefinition] = relationship()


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
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    field_definition_id: Mapped[int] = mapped_column(ForeignKey("field_definitions.id"))
    value: Mapped[str] = mapped_column(String(500))
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    employee: Mapped[Employee] = relationship(back_populates="overrides")
    field_definition: Mapped[FieldDefinition] = relationship(back_populates="overrides")


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
            "ix_employee_assignments_employee_field_start",
            "employee_id",
            "field_definition_id",
            "effective_from",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    field_definition_id: Mapped[int] = mapped_column(ForeignKey("field_definitions.id"))
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
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_datetime,
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    employee: Mapped[Employee] = relationship(back_populates="assignments")
    field_definition: Mapped[FieldDefinition] = relationship()
    source_policy_version: Mapped[PolicyVersion | None] = relationship()
    source_override: Mapped[EmployeeOverride | None] = relationship()
