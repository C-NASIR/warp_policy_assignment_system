from __future__ import annotations

from datetime import date
from typing import Literal

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database import Base


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
        default=date.today,
        server_default=func.current_date(),
    )
    policies: Mapped[list[Policy]] = relationship(secondary="employee_policies", back_populates="employees")
    assignments: Mapped[list[EmployeeAssignment]] = relationship(back_populates="employee", cascade="all, delete-orphan")


class FieldDefinition(Base):
    __tablename__ = "field_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    field: Mapped[str] = mapped_column(String(100), unique=True)
    # ``name`` keeps the current API backwards compatible while the persisted
    # field follows the domain vocabulary.
    name = synonym("field")
    cardinality: Mapped[Literal["one", "many"]] = mapped_column(String(10))
    conflict_resolution: Mapped[str] = mapped_column(String(50), default="priority")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    priority: Mapped[int]
    employees: Mapped[list[Employee]] = relationship(secondary="employee_policies", back_populates="policies")
    values: Mapped[list[PolicyFieldValue]] = relationship(back_populates="policy", cascade="all, delete-orphan")
    condition_groups: Mapped[list[ConditionGroup]] = relationship(
        back_populates="policy",
        cascade="all, delete-orphan",
    )
    compiled_clauses: Mapped[list[CompiledPolicyClause]] = relationship(
        back_populates="policy",
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
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"))
    parent_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("condition_groups.id", ondelete="CASCADE"),
        nullable=True,
    )
    logical_operator: Mapped[Literal["and", "or"]] = mapped_column(String(10))
    policy: Mapped[Policy] = relationship(back_populates="condition_groups")
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
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        index=True,
    )
    policy: Mapped[Policy] = relationship(back_populates="compiled_clauses")
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

    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True)
    field_definition_id: Mapped[int] = mapped_column(ForeignKey("field_definitions.id"), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), primary_key=True)
    policy: Mapped[Policy] = relationship(back_populates="values")
    field_definition: Mapped[FieldDefinition] = relationship()


class EmployeeAssignment(Base):
    __tablename__ = "employee_assignments"
    __table_args__ = (UniqueConstraint("employee_id", "field_definition_id", "value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    field_definition_id: Mapped[int] = mapped_column(ForeignKey("field_definitions.id"))
    value: Mapped[str] = mapped_column(String(500))
    source_policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"))
    employee: Mapped[Employee] = relationship(back_populates="assignments")
    field_definition: Mapped[FieldDefinition] = relationship()
    source_policy: Mapped[Policy] = relationship()
