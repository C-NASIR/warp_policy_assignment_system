import pytest
from sqlalchemy import select

from app.models import (
    CompiledPolicyClause,
    CompiledPolicyCondition,
    Employee,
    EmployeeOverride,
    FieldDefinition,
    Policy,
    PolicyFieldValue,
)
from app.services.employee_overrides import create_employee_override
from app.services.overrides import FinalAssignment, apply_employee_overrides
from app.services.policy_engine import PolicyConflictError, ResolvedAssignment
from app.services.policy_matching import refresh_employee_policies


def test_apply_employee_overrides_is_a_pure_field_replacement():
    resolved = [
        ResolvedAssignment(field_definition_id=1, value="weekly", source_policy_id=10),
        ResolvedAssignment(field_definition_id=2, value="GitHub", source_policy_id=20),
        ResolvedAssignment(field_definition_id=2, value="Slack", source_policy_id=21),
    ]
    overrides = [
        EmployeeOverride(id=7, employee_id=1, field_definition_id=1, value="monthly"),
        EmployeeOverride(id=8, employee_id=1, field_definition_id=3, value="gold"),
    ]

    assert apply_employee_overrides(resolved, overrides) == [
        FinalAssignment(1, "monthly", source_override_id=7),
        FinalAssignment(2, "GitHub", source_policy_id=20),
        FinalAssignment(2, "Slack", source_policy_id=21),
        FinalAssignment(3, "gold", source_override_id=8),
    ]


def test_override_creation_rolls_back_when_policy_resolution_conflicts(session_factory):
    with session_factory.begin() as session:
        employee = Employee(
            name="Alice",
            state="California",
            department="Engineering",
            employee_type="regular",
        )
        field = FieldDefinition(name="pay_schedule", cardinality="one")
        weekly = Policy(
            name="Weekly",
            priority=10,
            compiled_clauses=[
                CompiledPolicyClause(
                    conditions=[
                        CompiledPolicyCondition(
                            field="state",
                            operator="=",
                            value="California",
                        )
                    ]
                )
            ],
        )
        monthly = Policy(
            name="Monthly",
            priority=10,
            compiled_clauses=[
                CompiledPolicyClause(
                    conditions=[
                        CompiledPolicyCondition(
                            field="state",
                            operator="=",
                            value="California",
                        )
                    ]
                )
            ],
        )
        weekly.values = [PolicyFieldValue(field_definition=field, value="weekly")]
        monthly.values = [PolicyFieldValue(field_definition=field, value="monthly")]
        session.add_all([employee, weekly, monthly])
        session.flush()
        employee_id = employee.id
        field_id = field.id
        refresh_employee_policies(session, employee.id)

    with pytest.raises(PolicyConflictError):
        with session_factory.begin() as session:
            create_employee_override(
                session,
                employee_id,
                field_id,
                "quarterly",
            )

    with session_factory() as session:
        assert session.scalars(select(EmployeeOverride)).all() == []
