from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dates import current_datetime
from app.models import ChangeApprovalRequest, Policy
from app.schemas import (
    ChangeApprovalRequestRead,
    ChangePreviewCreate,
    ChangePreviewRead,
    PolicyStatusChangePreview,
)
from app.services.access_control import WILDCARD_PERMISSION
from app.services.audit import record_audit_log
from app.services.auth import AuthenticatedPrincipal
from app.services.change_approvals import (
    ChangeApprovalConflictError,
    change_digest,
    issue_change_approval,
    preview_digest,
)


def create_approval_request(
    session: Session,
    *,
    change: ChangePreviewCreate,
    preview: ChangePreviewRead,
    precondition_digest: str,
    principal: AuthenticatedPrincipal,
) -> ChangeApprovalRequest:
    request_id = str(uuid4())
    provisional = issue_change_approval(
        change,
        preview,
        precondition_digest,
        approval_id=request_id,
    )
    if provisional is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Change approval is not configured",
        )
    request = ChangeApprovalRequest(
        id=request_id,
        status="pending",
        change_type=change.type,
        change=change.model_dump(mode="json"),
        preview=preview.model_dump(
            mode="json",
            exclude={"approval", "approval_request_id"},
        ),
        change_digest=change_digest(change),
        precondition_digest=precondition_digest,
        preview_digest=preview_digest(preview),
        requested_by=principal.subject,
        requested_by_user_id=principal.user_id,
        expires_at=provisional.expires_at,
    )
    session.add(request)
    session.flush()
    _audit_request(session, request, "requested", principal.subject)
    return request


def approve_request(
    session: Session,
    request: ChangeApprovalRequest,
    *,
    change: ChangePreviewCreate,
    preview: ChangePreviewRead,
    principal: AuthenticatedPrincipal,
) -> ChangeApprovalRequest:
    _require_pending(request)
    if _same_human(request.requested_by_user_id, request.requested_by, principal):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Authors cannot approve their own changes",
        )
    if isinstance(change, PolicyStatusChangePreview):
        policy = session.get(Policy, change.policy_id)
        if policy is not None and policy.created_by == principal.subject:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The policy author cannot approve its lifecycle change",
            )
    approval = issue_change_approval(
        change,
        preview,
        request.precondition_digest,
        approval_id=request.id,
    )
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Change approval is not configured",
        )
    request.status = "approved"
    request.approved_by = principal.subject
    request.approved_by_user_id = principal.user_id
    request.approved_at = current_datetime()
    request.approval_token = approval.token
    request.expires_at = approval.expires_at
    session.flush()
    _audit_request(session, request, "approved", principal.subject)
    return request


def reject_request(
    session: Session,
    request: ChangeApprovalRequest,
    *,
    principal: AuthenticatedPrincipal,
) -> ChangeApprovalRequest:
    _require_pending(request)
    if _same_human(request.requested_by_user_id, request.requested_by, principal):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Authors cannot reject their own approval requests",
        )
    request.status = "rejected"
    request.rejected_by = principal.subject
    request.rejected_at = current_datetime()
    session.flush()
    _audit_request(session, request, "rejected", principal.subject)
    return request


def approval_request_read(
    session: Session,
    request: ChangeApprovalRequest,
    principal: AuthenticatedPrincipal,
) -> ChangeApprovalRequestRead:
    if request.status == "pending" and current_datetime() >= request.expires_at:
        request.status = "expired"
        session.flush()
        _audit_request(session, request, "expired", "system")
    is_root = WILDCARD_PERMISSION in principal.permissions
    different_author = not _same_human(
        request.requested_by_user_id,
        request.requested_by,
        principal,
    )
    can_approve_permission = _has_permission(principal, "changes:approve")
    can_execute_permission = _has_permission(principal, "changes:execute")
    return ChangeApprovalRequestRead(
        id=request.id,
        status=request.status,
        change_type=request.change_type,
        change=request.change,
        preview=request.preview,
        requested_by=request.requested_by,
        requested_by_user_id=request.requested_by_user_id,
        created_at=request.created_at,
        expires_at=request.expires_at,
        approved_by=request.approved_by,
        approved_by_user_id=request.approved_by_user_id,
        approved_at=request.approved_at,
        rejected_by=request.rejected_by,
        rejected_at=request.rejected_at,
        executed_at=request.executed_at,
        can_approve=(
            request.status == "pending"
            and different_author
            and can_approve_permission
        ),
        can_reject=(
            request.status == "pending"
            and different_author
            and can_approve_permission
        ),
        can_execute=(
            request.status == "approved"
            and can_execute_permission
            and (
                is_root
                or request.approved_by_user_id == principal.user_id
                or (
                    request.approved_by_user_id is None
                    and request.approved_by == principal.subject
                )
            )
        ),
    )


def require_approved_executor(
    request: ChangeApprovalRequest,
    principal: AuthenticatedPrincipal,
) -> None:
    same_approver = (
        WILDCARD_PERMISSION in principal.permissions
        or request.approved_by_user_id == principal.user_id
        or (
            request.approved_by_user_id is None
            and request.approved_by == principal.subject
        )
    )
    if (
        request.status in {"approved", "executed"}
        and _has_permission(principal, "changes:execute")
        and same_approver
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The approving user must execute this approved request",
    )


def mark_request_executed(
    session: Session,
    request: ChangeApprovalRequest,
    *,
    actor: str,
) -> None:
    request.status = "executed"
    request.executed_at = current_datetime()
    session.flush()
    _audit_request(session, request, "executed", actor)


def _require_pending(request: ChangeApprovalRequest) -> None:
    if request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval request is already {request.status}",
        )
    if current_datetime() >= request.expires_at:
        raise ChangeApprovalConflictError(
            "The approval request has expired",
            code="change_approval_expired",
            metadata={"approval_id": request.id},
        )


def _has_permission(principal: AuthenticatedPrincipal, permission: str) -> bool:
    return (
        WILDCARD_PERMISSION in principal.permissions
        or permission in principal.permissions
    )


def _same_human(
    user_id: int | None,
    subject: str,
    principal: AuthenticatedPrincipal,
) -> bool:
    if user_id is not None and principal.user_id is not None:
        return user_id == principal.user_id
    return subject == principal.subject


def _audit_request(
    session: Session,
    request: ChangeApprovalRequest,
    action: str,
    actor: str,
) -> None:
    record_audit_log(
        session,
        actor=actor,
        entity_type="ChangeApprovalRequest",
        entity_id=UUID(request.id).int % 2_147_483_647,
        action=action,
        before=None,
        after={
            "approval_request_id": request.id,
            "status": request.status,
            "change_type": request.change_type,
            "requested_by": request.requested_by,
            "approved_by": request.approved_by,
        },
    )
