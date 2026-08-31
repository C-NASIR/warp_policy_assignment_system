from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Mapper, Session

from app.models import (
    AuditLog,
    EmployeeAssignment,
    EmployeeOverride,
    PolicyVersion,
)

_SENSITIVE_FIELD_NAMES = {
    "access_token",
    "api_key",
    "password",
    "secret",
    "token",
}


def snapshot_entity(
    entity: object,
    *,
    exclude: Collection[str] = (),
    redact: Collection[str] = (),
) -> dict[str, Any]:
    """Return a JSON-safe snapshot of mapped scalar columns only."""
    excluded = set(exclude)
    redacted = _SENSITIVE_FIELD_NAMES | set(redact)
    snapshot: dict[str, Any] = {}
    mapper = cast(Mapper[Any], inspect(type(entity)))
    for column in mapper.columns:
        key = column.key
        if key in excluded:
            continue
        value = getattr(entity, key)
        snapshot[key] = "[REDACTED]" if key.lower() in redacted else _json_value(value)
    return snapshot


def snapshot_policy_version(version: PolicyVersion) -> dict[str, Any]:
    snapshot = snapshot_entity(version)
    snapshot["values"] = sorted(
        (
            {
                "assignment_field_definition_id": value.assignment_field_definition_id,
                "value": value.value,
            }
            for value in version.values
        ),
        key=lambda item: (item["assignment_field_definition_id"], item["value"]),
    )
    snapshot["compiled_clauses"] = [
        [
            {
                "field": condition.condition_field_definition.key,
                "operator": condition.operator,
                "value": condition.value,
            }
            for condition in sorted(clause.conditions, key=lambda item: item.id or 0)
        ]
        for clause in sorted(version.compiled_clauses, key=lambda item: item.id or 0)
    ]
    return snapshot


def snapshot_override(override: EmployeeOverride) -> dict[str, Any]:
    return snapshot_entity(override)


def snapshot_assignment(
    assignment: EmployeeAssignment,
    *,
    field_name: str | None = None,
) -> dict[str, Any]:
    snapshot = snapshot_entity(assignment)
    if field_name is not None:
        snapshot["field"] = field_name
    return snapshot


def record_audit_log(
    session: Session,
    *,
    actor: str,
    entity_type: str,
    entity_id: int,
    action: str,
    before: Mapping[str, Any] | list[Any] | None,
    after: Mapping[str, Any] | list[Any] | None,
    timestamp: datetime | None = None,
) -> AuditLog:
    actor = actor.strip()
    entity_type = entity_type.strip()
    action = action.strip()
    if not actor or len(actor) > 200:
        raise ValueError("Audit actor must contain 1 to 200 characters")
    if not entity_type or len(entity_type) > 100:
        raise ValueError("Audit entity_type must contain 1 to 100 characters")
    if not action or len(action) > 100:
        raise ValueError("Audit action must contain 1 to 100 characters")
    entry = AuditLog(
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=_json_value(before),
        after=_json_value(after),
    )
    if timestamp is not None:
        entry.timestamp = timestamp
    session.add(entry)
    session.flush()
    return entry


def list_audit_logs(
    session: Session,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor: str | None = None,
    action: str | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    statement = select(AuditLog)
    if entity_type is not None:
        statement = statement.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(AuditLog.entity_id == entity_id)
    if actor is not None:
        statement = statement.where(AuditLog.actor == actor)
    if action is not None:
        statement = statement.where(AuditLog.action == action)
    if from_timestamp is not None:
        statement = statement.where(AuditLog.timestamp >= from_timestamp)
    if to_timestamp is not None:
        statement = statement.where(AuditLog.timestamp <= to_timestamp)
    return list(
        session.scalars(
            statement.order_by(AuditLog.timestamp, AuditLog.id).offset(offset).limit(limit)
        )
    )


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, set):
        return [_json_value(item) for item in sorted(value, key=repr)]
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError(f"Audit snapshots cannot serialize {type(value).__name__}")
