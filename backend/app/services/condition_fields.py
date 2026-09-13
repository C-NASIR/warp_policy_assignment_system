from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ConditionFieldDefinition,
    ConditionFieldDependency,
    Employee,
)
from app.services.org_chart import (
    employee_direct_report_count,
    employee_is_manager,
    employee_management_level,
    get_ancestor_ids,
)
from app.states import normalize_state_code


class ConditionFieldError(ValueError):
    pass


@dataclass(frozen=True)
class CalendarDuration:
    years: int


@dataclass(frozen=True)
class TenureValue:
    start_date: date
    evaluation_date: date


@dataclass(frozen=True)
class ConditionFieldDependencySpec:
    dependency_type: Literal["column", "relationship", "time"]
    dependency_key: str
    source_table: str | None
    source_column: str | None
    role: str
    impact_resolver_key: str


@dataclass(frozen=True)
class ConditionFieldInputOptionSpec:
    value: str
    label: str


@dataclass(frozen=True)
class ConditionFieldInputSpec:
    type: Literal["text", "date", "number", "select", "duration", "resource"]
    allows_null: bool = False
    placeholder: str | None = None
    options: tuple[ConditionFieldInputOptionSpec, ...] = ()
    reference_resource: str | None = None
    minimum: int | None = None


Resolver = Callable[["ConditionEvaluationContext"], Any]
Parser = Callable[[str], tuple[str, Any]]
Comparator = Callable[[Any, str, Any], bool]


@dataclass(frozen=True)
class ConditionFieldSpec:
    key: str
    label: str
    description: str
    field_type: Literal["static", "derived"]
    data_type: str
    resolver_key: str
    allowed_operators: tuple[str, ...]
    input: ConditionFieldInputSpec
    resolver: Resolver
    parser: Parser
    comparator: Comparator | None = None
    source_table: str | None = None
    source_column: str | None = None
    dependencies: tuple[ConditionFieldDependencySpec, ...] = ()


@dataclass
class ConditionEvaluationContext:
    session: Session
    employee: Employee
    evaluation_date: date
    _cache: dict[str, Any] = field(default_factory=dict)

    def resolve(self, spec: ConditionFieldSpec) -> Any:
        if spec.key not in self._cache:
            self._cache[spec.key] = spec.resolver(self)
        return self._cache[spec.key]


@dataclass(frozen=True)
class ConditionEvaluation:
    result: bool
    actual: Any
    expected: Any


_COMPARABLE_OPERATORS = ("=", "<", "<=", ">", ">=")
_EQUALITY_OPERATORS = ("=",)
_DURATION_PATTERN = re.compile(
    r"^(?:P(?P<iso>\d+)Y|(?P<human>\d+)\s+years?)$", re.IGNORECASE
)


def _string_parser(value: str) -> tuple[str, str]:
    return value, value


def _state_parser(value: str) -> tuple[str, str]:
    try:
        normalized = normalize_state_code(value)
    except ValueError as exc:
        raise ConditionFieldError(str(exc)) from exc
    return normalized, normalized


def _date_parser(value: str) -> tuple[str, date]:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ConditionFieldError(
            "condition value must be an ISO date (YYYY-MM-DD)"
        ) from exc
    return parsed.isoformat(), parsed


def _positive_integer_parser(value: str) -> tuple[str, int]:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConditionFieldError("condition value must be a positive integer") from exc
    if parsed <= 0:
        raise ConditionFieldError("condition value must be a positive integer")
    return str(parsed), parsed


def _nonnegative_integer_parser(value: str) -> tuple[str, int]:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConditionFieldError(
            "condition value must be a nonnegative integer"
        ) from exc
    if parsed < 0:
        raise ConditionFieldError("condition value must be a nonnegative integer")
    return str(parsed), parsed


def _boolean_parser(value: str) -> tuple[str, bool]:
    normalized = value.strip().lower()
    if normalized == "true":
        return normalized, True
    if normalized == "false":
        return normalized, False
    raise ConditionFieldError("condition value must be 'true' or 'false'")


def _calendar_duration_parser(value: str) -> tuple[str, CalendarDuration]:
    match = _DURATION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ConditionFieldError(
            "tenure condition values must be whole calendar years, such as '2 years' or 'P2Y'"
        )
    years = int(match.group("iso") or match.group("human"))
    if years <= 0:
        raise ConditionFieldError("tenure condition years must be positive")
    return f"P{years}Y", CalendarDuration(years=years)


def _static_resolver(attribute: str) -> Resolver:
    def resolve(context: ConditionEvaluationContext) -> Any:
        return getattr(context.employee, attribute)

    return resolve


def _resolve_tenure(context: ConditionEvaluationContext) -> TenureValue:
    return TenureValue(
        start_date=context.employee.start_date,
        evaluation_date=context.evaluation_date,
    )


def _resolve_is_manager(context: ConditionEvaluationContext) -> bool:
    return employee_is_manager(context.session, context.employee.id)


def _resolve_direct_report_count(context: ConditionEvaluationContext) -> int:
    return employee_direct_report_count(context.session, context.employee.id)


def _resolve_reports_under(context: ConditionEvaluationContext) -> frozenset[int]:
    return frozenset(get_ancestor_ids(context.session, context.employee.id))


def _resolve_management_level(context: ConditionEvaluationContext) -> int:
    return employee_management_level(context.session, context.employee.id)


def _contains_reference(actual: Any, operator: str, expected: Any) -> bool:
    return operator == "=" and expected in actual


def _employee_column_dependency(
    column: str,
) -> tuple[ConditionFieldDependencySpec, ...]:
    return (
        ConditionFieldDependencySpec(
            dependency_type="column",
            dependency_key=f"employee.{column}",
            source_table="employees",
            source_column=column,
            role="value",
            impact_resolver_key="changed_employee",
        ),
    )


def _manager_relationship_dependency(
    impact_resolver_key: str,
    role: str,
) -> tuple[ConditionFieldDependencySpec, ...]:
    return (
        ConditionFieldDependencySpec(
            dependency_type="relationship",
            dependency_key="employee.manager_id",
            source_table="employees",
            source_column="manager_id",
            role=role,
            impact_resolver_key=impact_resolver_key,
        ),
    )


def _static_spec(
    key: str,
    label: str,
    description: str,
    data_type: str,
    parser: Parser,
    input: ConditionFieldInputSpec,
) -> ConditionFieldSpec:
    return ConditionFieldSpec(
        key=key,
        label=label,
        description=description,
        field_type="static",
        data_type=data_type,
        resolver_key=f"employee_attribute_{key}_v1",
        allowed_operators=_COMPARABLE_OPERATORS,
        input=input,
        resolver=_static_resolver(key),
        parser=parser,
        source_table="employees",
        source_column=key,
        dependencies=_employee_column_dependency(key),
    )


CONDITION_FIELD_SPECS = {
    spec.key: spec
    for spec in (
        ConditionFieldSpec(
            key="employee_id",
            label="Employee",
            description="A specific employee, identified by their stable employee ID.",
            field_type="static",
            data_type="employee_reference",
            resolver_key="employee_attribute_id_v1",
            allowed_operators=_EQUALITY_OPERATORS,
            input=ConditionFieldInputSpec(
                type="resource",
                reference_resource="employees",
            ),
            resolver=_static_resolver("id"),
            parser=_positive_integer_parser,
            source_table="employees",
            source_column="id",
            dependencies=_employee_column_dependency("id"),
        ),
        _static_spec(
            "name",
            "Employee name",
            "The employee's full name.",
            "string",
            _string_parser,
            ConditionFieldInputSpec(type="text", placeholder="Alice Johnson"),
        ),
        ConditionFieldSpec(
            key="state",
            label="State",
            description="The employee's U.S. state or territory of employment.",
            field_type="static",
            data_type="state_code",
            resolver_key="employee_attribute_state_v1",
            allowed_operators=_EQUALITY_OPERATORS,
            input=ConditionFieldInputSpec(
                type="resource",
                reference_resource="states",
            ),
            resolver=_static_resolver("state"),
            parser=_state_parser,
            source_table="employees",
            source_column="state",
            dependencies=_employee_column_dependency("state"),
        ),
        _static_spec(
            "department",
            "Department",
            "The employee's current department.",
            "string",
            _string_parser,
            ConditionFieldInputSpec(
                type="resource",
                reference_resource="departments",
            ),
        ),
        _static_spec(
            "employee_type",
            "Employee type",
            "The employee's employment classification.",
            "string",
            _string_parser,
            ConditionFieldInputSpec(
                type="resource",
                reference_resource="employee_types",
            ),
        ),
        _static_spec(
            "location",
            "Location",
            "The employee's work location.",
            "string",
            _string_parser,
            ConditionFieldInputSpec(type="text", placeholder="New York Office"),
        ),
        _static_spec(
            "start_date",
            "Start date",
            "The employee's employment start date.",
            "date",
            _date_parser,
            ConditionFieldInputSpec(type="date", placeholder="2026-01-15"),
        ),
        ConditionFieldSpec(
            key="manager_id",
            label="Manager",
            description="The employee's direct manager.",
            field_type="static",
            data_type="employee_reference",
            resolver_key="employee_attribute_manager_id_v1",
            allowed_operators=_EQUALITY_OPERATORS,
            input=ConditionFieldInputSpec(
                type="resource",
                reference_resource="employees",
            ),
            resolver=_static_resolver("manager_id"),
            parser=_positive_integer_parser,
            source_table="employees",
            source_column="manager_id",
            dependencies=_employee_column_dependency("manager_id"),
        ),
        ConditionFieldSpec(
            key="is_manager",
            label="Is manager",
            description="Whether the employee currently has direct reports.",
            field_type="derived",
            data_type="boolean",
            resolver_key="employee_is_manager_v1",
            allowed_operators=_EQUALITY_OPERATORS,
            input=ConditionFieldInputSpec(
                type="select",
                options=(
                    ConditionFieldInputOptionSpec(value="true", label="True"),
                    ConditionFieldInputOptionSpec(value="false", label="False"),
                ),
            ),
            resolver=_resolve_is_manager,
            parser=_boolean_parser,
            dependencies=_manager_relationship_dependency(
                "old_and_new_managers",
                "direct_reports",
            ),
        ),
        ConditionFieldSpec(
            key="direct_report_count",
            label="Direct report count",
            description="The employee's current number of direct reports.",
            field_type="derived",
            data_type="integer",
            resolver_key="employee_direct_report_count_v1",
            allowed_operators=_COMPARABLE_OPERATORS,
            input=ConditionFieldInputSpec(
                type="number",
                placeholder="5",
                minimum=0,
            ),
            resolver=_resolve_direct_report_count,
            parser=_nonnegative_integer_parser,
            dependencies=_manager_relationship_dependency(
                "old_and_new_managers",
                "direct_report_count",
            ),
        ),
        ConditionFieldSpec(
            key="reports_under",
            label="Reports under",
            description=(
                "Whether the employee reports directly or indirectly to the "
                "selected manager."
            ),
            field_type="derived",
            data_type="employee_reference",
            resolver_key="employee_manager_chain_v1",
            allowed_operators=_EQUALITY_OPERATORS,
            input=ConditionFieldInputSpec(
                type="resource",
                reference_resource="employees",
            ),
            resolver=_resolve_reports_under,
            parser=_positive_integer_parser,
            comparator=_contains_reference,
            dependencies=_manager_relationship_dependency(
                "moved_subtree",
                "ancestor_chain",
            ),
        ),
        ConditionFieldSpec(
            key="management_level",
            label="Management level",
            description=(
                "The employee's number of reporting hops from the root of the "
                "org chart."
            ),
            field_type="derived",
            data_type="integer",
            resolver_key="employee_management_level_v1",
            allowed_operators=_COMPARABLE_OPERATORS,
            input=ConditionFieldInputSpec(
                type="number",
                placeholder="2",
                minimum=0,
            ),
            resolver=_resolve_management_level,
            parser=_nonnegative_integer_parser,
            dependencies=_manager_relationship_dependency(
                "moved_subtree",
                "ancestor_depth",
            ),
        ),
        ConditionFieldSpec(
            key="tenure",
            label="Tenure",
            description="The employee's completed whole calendar years of tenure.",
            field_type="derived",
            data_type="calendar_duration",
            resolver_key="employee_tenure_v1",
            allowed_operators=_COMPARABLE_OPERATORS,
            input=ConditionFieldInputSpec(
                type="duration",
                placeholder="2 years",
                minimum=1,
            ),
            resolver=_resolve_tenure,
            parser=_calendar_duration_parser,
            dependencies=(
                ConditionFieldDependencySpec(
                    dependency_type="column",
                    dependency_key="employee.start_date",
                    source_table="employees",
                    source_column="start_date",
                    role="tenure_origin",
                    impact_resolver_key="changed_employee",
                ),
                ConditionFieldDependencySpec(
                    dependency_type="time",
                    dependency_key="evaluation_date",
                    source_table=None,
                    source_column=None,
                    role="clock",
                    impact_resolver_key="tenure_threshold_schedule",
                ),
            ),
        ),
    )
}


def normalize_condition(field_key: str, operator: str, value: str) -> str:
    spec = CONDITION_FIELD_SPECS.get(field_key)
    if spec is None:
        raise ConditionFieldError(f"Unsupported condition field: {field_key}")
    if operator not in spec.allowed_operators:
        raise ConditionFieldError(
            f"Operator '{operator}' is not supported for condition field '{field_key}'"
        )
    normalized, _ = spec.parser(value)
    return normalized


def evaluate_condition(
    context: ConditionEvaluationContext,
    definition: ConditionFieldDefinition,
    operator: str,
    value: str,
) -> bool:
    return evaluate_condition_with_evidence(
        context,
        definition,
        operator,
        value,
    ).result


def evaluate_condition_with_evidence(
    context: ConditionEvaluationContext,
    definition: ConditionFieldDefinition,
    operator: str,
    value: str,
) -> ConditionEvaluation:
    spec = CONDITION_FIELD_SPECS.get(definition.key)
    if (
        spec is None
        or not definition.active
        or definition.resolver_key != spec.resolver_key
    ):
        return ConditionEvaluation(False, None, value)
    if operator not in spec.allowed_operators:
        return ConditionEvaluation(False, None, value)
    try:
        _, expected = spec.parser(value)
    except ConditionFieldError:
        return ConditionEvaluation(False, None, value)
    actual = context.resolve(spec)
    if actual is None:
        return ConditionEvaluation(False, None, _explanation_value(expected))
    if spec.comparator is not None:
        result = spec.comparator(actual, operator, expected)
    elif isinstance(actual, TenureValue) and isinstance(expected, CalendarDuration):
        result = _compare_tenure(actual, operator, expected)
    else:
        result = _compare(actual, operator, expected)
    return ConditionEvaluation(
        result,
        _explanation_value(actual),
        _explanation_value(expected),
    )


def _explanation_value(value: Any) -> Any:
    if isinstance(value, TenureValue):
        return {
            "start_date": value.start_date.isoformat(),
            "evaluation_date": value.evaluation_date.isoformat(),
        }
    if isinstance(value, CalendarDuration):
        return f"P{value.years}Y"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (set, frozenset, tuple)):
        return sorted(value)
    return value


def add_calendar_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        # February 29 reaches its anniversary on February 28 in non-leap years.
        return day.replace(year=day.year + years, day=28)


def tenure_transition_dates(
    start_date: date,
    operator: str,
    normalized_value: str,
) -> tuple[date, ...]:
    _, duration = _calendar_duration_parser(normalized_value)
    years = duration.years
    transition_years = {
        "=": (years, years + 1),
        "<": (years,),
        "<=": (years + 1,),
        ">": (years + 1,),
        ">=": (years,),
    }.get(operator, ())
    return tuple(add_calendar_years(start_date, item) for item in transition_years)


def sync_condition_field_definitions(
    session: Session,
) -> list[ConditionFieldDefinition]:
    existing = {
        item.key: item
        for item in session.scalars(
            select(ConditionFieldDefinition).options(
                selectinload(ConditionFieldDefinition.dependencies)
            )
        )
    }
    for definition in existing.values():
        if definition.key not in CONDITION_FIELD_SPECS:
            definition.active = False

    synchronized: list[ConditionFieldDefinition] = []
    for spec in CONDITION_FIELD_SPECS.values():
        definition = existing.get(spec.key)
        if definition is None:
            definition = ConditionFieldDefinition(key=spec.key)
            session.add(definition)
        definition.label = spec.label
        definition.description = spec.description
        definition.field_type = spec.field_type
        definition.data_type = spec.data_type
        definition.allowed_operators = list(spec.allowed_operators)
        definition.input = {
            "type": spec.input.type,
            "allows_null": spec.input.allows_null,
            "placeholder": spec.input.placeholder,
            "options": [
                {"value": option.value, "label": option.label}
                for option in spec.input.options
            ],
            "reference_resource": spec.input.reference_resource,
            "minimum": spec.input.minimum,
        }
        definition.resolver_key = spec.resolver_key
        definition.source_table = spec.source_table
        definition.source_column = spec.source_column
        definition.active = True
        existing_dependencies = {
            (item.dependency_key, item.role): item for item in definition.dependencies
        }
        desired_dependency_keys: set[tuple[str, str]] = set()
        for item in spec.dependencies:
            dependency_key = (item.dependency_key, item.role)
            desired_dependency_keys.add(dependency_key)
            dependency = existing_dependencies.get(dependency_key)
            if dependency is None:
                dependency = ConditionFieldDependency(
                    dependency_key=item.dependency_key,
                    role=item.role,
                )
                definition.dependencies.append(dependency)
            dependency.dependency_type = item.dependency_type
            dependency.source_table = item.source_table
            dependency.source_column = item.source_column
            dependency.impact_resolver_key = item.impact_resolver_key
        for dependency_key, dependency in existing_dependencies.items():
            if dependency_key not in desired_dependency_keys:
                session.delete(dependency)
        synchronized.append(definition)
    session.flush()
    return synchronized


def get_condition_field_definitions(
    session: Session,
    field_keys: set[str],
) -> dict[str, ConditionFieldDefinition]:
    definitions = {
        item.key: item
        for item in session.scalars(
            select(ConditionFieldDefinition).where(
                ConditionFieldDefinition.key.in_(field_keys),
                ConditionFieldDefinition.active.is_(True),
            )
        )
    }
    missing = sorted(field_keys - definitions.keys())
    if missing:
        raise ConditionFieldError(f"Condition fields not found: {missing}")
    return definitions


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "=":
        return actual == expected
    if operator == "<":
        return actual < expected
    if operator == "<=":
        return actual <= expected
    if operator == ">":
        return actual > expected
    if operator == ">=":
        return actual >= expected
    return False


def _compare_tenure(
    tenure: TenureValue,
    operator: str,
    expected: CalendarDuration,
) -> bool:
    threshold = add_calendar_years(tenure.start_date, expected.years)
    next_threshold = add_calendar_years(tenure.start_date, expected.years + 1)
    if operator == "=":
        return threshold <= tenure.evaluation_date < next_threshold
    if operator == "<":
        return tenure.evaluation_date < threshold
    if operator == "<=":
        return tenure.evaluation_date < next_threshold
    if operator == ">":
        return tenure.evaluation_date >= next_threshold
    if operator == ">=":
        return tenure.evaluation_date >= threshold
    return False
