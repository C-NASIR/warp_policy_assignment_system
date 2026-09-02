from __future__ import annotations

from typing import Any, Literal

from fastapi.encoders import jsonable_encoder

from app.schemas import APIErrorIssueRead, APIErrorRead, APIErrorResponseRead
from app.services.employee_overrides import EmployeeOverrideConflictError
from app.services.org_chart import EmployeeHierarchyConflictError
from app.services.policy_engine import PolicyConflictError
from app.services.policy_versions import (
    EffectivePolicyVersionConflictError,
    PolicyVersionOverlapError,
)
from app.services.reconciliation import AssignmentReconciliationOrderError


def conflict_code(exc: Exception) -> str:
    if isinstance(exc, PolicyVersionOverlapError):
        return "policy_version_overlap"
    if isinstance(exc, EffectivePolicyVersionConflictError):
        return "effective_policy_version_conflict"
    if isinstance(exc, EmployeeOverrideConflictError):
        return "employee_override_conflict"
    if isinstance(exc, EmployeeHierarchyConflictError):
        return "employee_hierarchy_conflict"
    if isinstance(exc, AssignmentReconciliationOrderError):
        return "assignment_reconciliation_order_conflict"
    if isinstance(exc, PolicyConflictError):
        return "policy_conflict"
    return "conflict"


def conflict_issue(exc: Exception) -> APIErrorIssueRead:
    return APIErrorIssueRead(
        code=conflict_code(exc),
        message=str(exc),
        path=_conflict_path(exc),
        metadata=jsonable_encoder(getattr(exc, "metadata", {})),
    )


def conflict_response(exc: Exception) -> dict[str, Any]:
    issue = conflict_issue(exc)
    return error_response(
        category="conflict",
        code=issue.code,
        message=issue.message,
        issues=[issue],
        legacy_detail=issue.message,
    )


def validation_response(
    *,
    issues: list[APIErrorIssueRead],
    legacy_detail: Any,
) -> dict[str, Any]:
    return error_response(
        category="validation",
        code="request_validation_failed",
        message="Request validation failed",
        issues=issues,
        legacy_detail=legacy_detail,
    )


def error_response(
    *,
    category: Literal[
        "validation",
        "conflict",
        "authentication",
        "authorization",
    ],
    code: str,
    message: str,
    issues: list[APIErrorIssueRead],
    legacy_detail: Any,
) -> dict[str, Any]:
    return APIErrorResponseRead(
        detail=jsonable_encoder(legacy_detail),
        error=APIErrorRead(
            category=category,
            code=code,
            message=message,
            issues=issues,
        ),
    ).model_dump(mode="json")


def validation_issue(
    *,
    code: str,
    message: str,
    path: list[str | int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> APIErrorIssueRead:
    return APIErrorIssueRead(
        code=code,
        message=message,
        path=path or [],
        metadata=jsonable_encoder(metadata or {}),
    )


def _conflict_path(exc: Exception) -> list[str | int]:
    if isinstance(exc, PolicyConflictError) and exc.assignment_field_name:
        return ["assignments", exc.assignment_field_name]
    metadata = getattr(exc, "metadata", {})
    if isinstance(exc, EmployeeOverrideConflictError):
        return [
            "employees",
            metadata.get("employee_id", "unknown"),
            "overrides",
            metadata.get("assignment_field_name", "unknown"),
        ]
    if isinstance(exc, EmployeeHierarchyConflictError):
        return ["employees", metadata.get("employee_id", "unknown"), "manager_id"]
    if isinstance(
        exc,
        (PolicyVersionOverlapError, EffectivePolicyVersionConflictError),
    ):
        return ["policies", metadata.get("policy_id", "unknown"), "versions"]
    if isinstance(exc, AssignmentReconciliationOrderError):
        return ["employees", metadata.get("employee_id", "unknown"), "assignments"]
    return []
