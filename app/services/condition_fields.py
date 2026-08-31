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


Resolver = Callable[["ConditionEvaluationContext"], Any]
Parser = Callable[[str], tuple[str, Any]]


@dataclass(frozen=True)
class ConditionFieldSpec:
    key: str
    label: str
    field_type: Literal["static", "derived"]
    data_type: str
    resolver_key: str
    allowed_operators: frozenset[str]
    resolver: Resolver
    parser: Parser
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


_COMPARABLE_OPERATORS = frozenset({"=", "<", "<=", ">", ">="})
_DURATION_PATTERN = re.compile(r"^(?:P(?P<iso>\d+)Y|(?P<human>\d+)\s+years?)$", re.IGNORECASE)


def _string_parser(value: str) -> tuple[str, str]:
    return value, value


def _date_parser(value: str) -> tuple[str, date]:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ConditionFieldError("condition value must be an ISO date (YYYY-MM-DD)") from exc
    return parsed.isoformat(), parsed


def _positive_integer_parser(value: str) -> tuple[str, int]:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConditionFieldError("condition value must be a positive integer") from exc
    if parsed <= 0:
        raise ConditionFieldError("condition value must be a positive integer")
    return str(parsed), parsed


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


def _employee_column_dependency(column: str) -> tuple[ConditionFieldDependencySpec, ...]:
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


def _static_spec(
    key: str,
    label: str,
    data_type: str,
    parser: Parser,
) -> ConditionFieldSpec:
    return ConditionFieldSpec(
        key=key,
        label=label,
        field_type="static",
        data_type=data_type,
        resolver_key=f"employee_attribute_{key}_v1",
        allowed_operators=_COMPARABLE_OPERATORS,
        resolver=_static_resolver(key),
        parser=parser,
        source_table="employees",
        source_column=key,
        dependencies=_employee_column_dependency(key),
    )


CONDITION_FIELD_SPECS = {
    spec.key: spec
    for spec in (
        _static_spec("name", "Name", "string", _string_parser),
        _static_spec("state", "State", "string", _string_parser),
        _static_spec("department", "Department", "string", _string_parser),
        _static_spec("employee_type", "Employee type", "string", _string_parser),
        _static_spec("location", "Location", "string", _string_parser),
        _static_spec("start_date", "Start date", "date", _date_parser),
        _static_spec("manager_id", "Manager ID", "integer", _positive_integer_parser),
        ConditionFieldSpec(
            key="tenure",
            label="Tenure",
            field_type="derived",
            data_type="calendar_duration",
            resolver_key="employee_tenure_v1",
            allowed_operators=_COMPARABLE_OPERATORS,
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
    spec = CONDITION_FIELD_SPECS.get(definition.key)
    if spec is None or not definition.active or definition.resolver_key != spec.resolver_key:
        return False
    if operator not in spec.allowed_operators:
        return False
    try:
        _, expected = spec.parser(value)
    except ConditionFieldError:
        return False
    actual = context.resolve(spec)
    if actual is None:
        return False
    if isinstance(actual, TenureValue) and isinstance(expected, CalendarDuration):
        return _compare_tenure(actual, operator, expected)
    return _compare(actual, operator, expected)


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


def sync_condition_field_definitions(session: Session) -> list[ConditionFieldDefinition]:
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
        definition.field_type = spec.field_type
        definition.data_type = spec.data_type
        definition.resolver_key = spec.resolver_key
        definition.source_table = spec.source_table
        definition.source_column = spec.source_column
        definition.active = True
        existing_dependencies = {
            (item.dependency_key, item.role): item
            for item in definition.dependencies
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
