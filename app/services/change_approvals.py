from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.dates import current_datetime
from app.models import (
    Employee,
    EmployeeGroupMembership,
    EmployeeOverride,
    Group,
    GroupPolicy,
    Policy,
    PolicyVersion,
)
from app.schemas import (
    ChangeApprovalRead,
    ChangePreviewCreate,
    ChangePreviewRead,
    EmployeeCreateChangePreview,
    EmployeeOverrideChangePreview,
    EmployeeUpdateChangePreview,
    GroupMembershipChangePreview,
    PolicyVersionCreateChangePreview,
)
from app.services.audit import (
    snapshot_entity,
    snapshot_override,
    snapshot_policy_version,
)

_TOKEN_VERSION = 1
_DEFAULT_TTL_SECONDS = 900


class ChangeApprovalValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "change_approval_token_invalid",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.metadata = metadata or {}


class ChangeApprovalConflictError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.metadata = metadata or {}


@dataclass(frozen=True)
class ChangeApprovalClaims:
    approval_id: str
    issued_at: datetime
    expires_at: datetime
    change_digest: str
    precondition_digest: str
    preview_digest: str


def issue_change_approval(
    change: ChangePreviewCreate,
    preview: ChangePreviewRead,
    precondition_digest: str,
) -> ChangeApprovalRead | None:
    secret = _approval_secret()
    if secret is None:
        return None
    issued_at = current_datetime().replace(microsecond=0)
    expires_at = issued_at + timedelta(seconds=_approval_ttl_seconds())
    payload = {
        "version": _TOKEN_VERSION,
        "approval_id": str(uuid4()),
        "issued_at": int(issued_at.timestamp()),
        "expires_at": int(expires_at.timestamp()),
        "change_digest": change_digest(change),
        "precondition_digest": precondition_digest,
        "preview_digest": preview_digest(preview),
    }
    encoded_payload = _base64url_encode(_canonical_json(payload))
    signature = hmac.new(
        secret,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    token = f"{encoded_payload}.{_base64url_encode(signature)}"
    return ChangeApprovalRead(
        approval_id=payload["approval_id"],
        token=token,
        issued_at=issued_at,
        expires_at=expires_at,
        change_digest=payload["change_digest"],
        precondition_digest=payload["precondition_digest"],
        preview_digest=payload["preview_digest"],
    )


def verify_change_approval(
    token: str,
    *,
    check_expiration: bool = True,
) -> ChangeApprovalClaims:
    secret = _approval_secret()
    if secret is None:
        raise ChangeApprovalValidationError(
            "Approved-change execution is not configured",
            code="change_approval_not_configured",
        )
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        supplied_signature = _base64url_decode(encoded_signature)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise ChangeApprovalValidationError(
            "The change approval token is malformed"
        ) from exc
    expected_signature = hmac.new(
        secret,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise ChangeApprovalValidationError(
            "The change approval token signature is invalid"
        )
    try:
        payload = json.loads(_base64url_decode(encoded_payload))
        if payload["version"] != _TOKEN_VERSION:
            raise ValueError("unsupported token version")
        claims = ChangeApprovalClaims(
            approval_id=str(payload["approval_id"]),
            issued_at=datetime.fromtimestamp(int(payload["issued_at"]), tz=UTC),
            expires_at=datetime.fromtimestamp(int(payload["expires_at"]), tz=UTC),
            change_digest=_require_digest(payload["change_digest"]),
            precondition_digest=_require_digest(payload["precondition_digest"]),
            preview_digest=_require_digest(payload["preview_digest"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ChangeApprovalValidationError(
            "The change approval token payload is invalid"
        ) from exc
    if check_expiration:
        validate_approval_not_expired(claims)
    return claims


def validate_approval_not_expired(claims: ChangeApprovalClaims) -> None:
    if current_datetime() < claims.expires_at:
        return
    raise ChangeApprovalConflictError(
        "The approved change has expired; create and approve a new preview",
        code="change_approval_expired",
        metadata={
            "approval_id": claims.approval_id,
            "expired_at": claims.expires_at.isoformat(),
        },
    )


def validate_approved_change(
    claims: ChangeApprovalClaims,
    change: ChangePreviewCreate,
) -> None:
    submitted_digest = change_digest(change)
    if not hmac.compare_digest(submitted_digest, claims.change_digest):
        raise ChangeApprovalConflictError(
            "The submitted change does not match the approved preview",
            code="change_approval_change_mismatch",
            metadata={
                "approval_id": claims.approval_id,
                "approved_change_digest": claims.change_digest,
                "submitted_change_digest": submitted_digest,
            },
        )


def change_digest(change: ChangePreviewCreate) -> str:
    return _digest(change.model_dump(mode="json"))


def preview_digest(preview: ChangePreviewRead) -> str:
    return _digest(preview.model_dump(mode="json", exclude={"approval"}))


def precondition_digest(value: Any) -> str:
    return _digest(value)


def lock_approval_execution(session: Session, approval_id: str) -> None:
    if session.get_bind().dialect.name != "postgresql":
        return
    lock_key = int.from_bytes(
        hashlib.sha256(approval_id.encode("utf-8")).digest()[:8],
        byteorder="big",
        signed=True,
    )
    session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key},
    )


def change_precondition_digest(
    session: Session,
    change: ChangePreviewCreate,
    *,
    lock: bool,
) -> str:
    if isinstance(change, EmployeeCreateChangePreview):
        state: Any = {"change_type": change.type}
    elif isinstance(change, EmployeeUpdateChangePreview):
        statement = select(Employee).where(Employee.id == change.employee_id)
        if lock:
            statement = statement.with_for_update()
        employee = session.scalar(statement)
        state = {
            "employee": snapshot_entity(employee) if employee is not None else None
        }
    elif isinstance(change, PolicyVersionCreateChangePreview):
        policy_statement = select(Policy).where(Policy.id == change.policy_id)
        versions_statement = (
            select(PolicyVersion)
            .where(PolicyVersion.policy_id == change.policy_id)
            .order_by(PolicyVersion.version_number)
        )
        if lock:
            policy_statement = policy_statement.with_for_update()
            versions_statement = versions_statement.with_for_update()
        policy = session.scalar(policy_statement)
        versions = list(session.scalars(versions_statement))
        state = {
            "policy": snapshot_entity(policy) if policy is not None else None,
            "versions": [snapshot_policy_version(version) for version in versions],
        }
    elif isinstance(change, GroupMembershipChangePreview):
        group_statement = select(Group).where(Group.id == change.group_id)
        employee_statement = select(Employee).where(
            Employee.id == change.employee_id
        )
        if lock:
            group_statement = group_statement.with_for_update()
            employee_statement = employee_statement.with_for_update()
        group = session.scalar(group_statement)
        employee = session.scalar(employee_statement)
        membership = session.get(
            EmployeeGroupMembership,
            {"group_id": change.group_id, "employee_id": change.employee_id},
        )
        state = {
            "group": snapshot_entity(group) if group is not None else None,
            "employee": snapshot_entity(employee) if employee is not None else None,
            "membership_exists": membership is not None,
            "group_policy_ids": sorted(
                session.scalars(
                    select(GroupPolicy.policy_id).where(
                        GroupPolicy.group_id == change.group_id
                    )
                )
            ),
        }
    elif isinstance(change, EmployeeOverrideChangePreview):
        employee_statement = select(Employee.id).where(
            Employee.id == change.employee_id
        )
        overrides_statement = (
            select(EmployeeOverride)
            .where(
                EmployeeOverride.employee_id == change.employee_id,
                EmployeeOverride.retired_at.is_(None),
            )
            .order_by(EmployeeOverride.id)
        )
        if lock:
            employee_statement = employee_statement.with_for_update()
            overrides_statement = overrides_statement.with_for_update()
        state = {
            "employee_exists": session.scalar(employee_statement) is not None,
            "active_overrides": [
                snapshot_override(override)
                for override in session.scalars(overrides_statement)
            ],
        }
    else:
        raise ValueError(f"Unsupported approved change type: {change.type}")
    return precondition_digest(state)


def _approval_secret() -> bytes | None:
    value = os.getenv("CHANGE_APPROVAL_SECRET")
    if value is None or not value.strip():
        return None
    secret = value.encode("utf-8")
    return secret if len(secret) >= 32 else None


def _approval_ttl_seconds() -> int:
    raw = os.getenv("CHANGE_APPROVAL_TTL_SECONDS")
    if raw is None:
        return _DEFAULT_TTL_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_TTL_SECONDS
    return min(max(value, 60), 3600)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _require_digest(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("invalid digest")
    int(value, 16)
    return value
