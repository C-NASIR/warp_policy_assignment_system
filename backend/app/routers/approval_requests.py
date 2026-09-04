from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import TypeAdapter
from sqlalchemy import select

from app.dependencies import Authenticated, DatabaseSession
from app.models import ChangeApprovalRequest
from app.schemas import (
    ChangeApprovalRequestRead,
    ChangePreviewCreate,
    ChangePreviewRead,
)
from app.services.approval_requests import (
    approval_request_read,
    approve_request,
    reject_request,
)

router = APIRouter(prefix="/approval-requests", tags=["approval requests"])


@router.get("", response_model=list[ChangeApprovalRequestRead])
def list_approval_requests(
    session: DatabaseSession,
    principal: Authenticated,
    request_status: Annotated[
        Literal["pending", "approved", "rejected", "executed", "expired"] | None,
        Query(alias="status"),
    ] = None,
) -> list[ChangeApprovalRequestRead]:
    statement = select(ChangeApprovalRequest)
    if request_status is not None:
        statement = statement.where(ChangeApprovalRequest.status == request_status)
    requests = list(
        session.scalars(
            statement.order_by(
                ChangeApprovalRequest.created_at.desc(),
                ChangeApprovalRequest.id,
            )
        )
    )
    return [approval_request_read(session, request, principal) for request in requests]


@router.get("/{request_id}", response_model=ChangeApprovalRequestRead)
def get_approval_request(
    request_id: str,
    session: DatabaseSession,
    principal: Authenticated,
) -> ChangeApprovalRequestRead:
    return approval_request_read(
        session,
        _request_or_404(session, request_id),
        principal,
    )


@router.post("/{request_id}/approve", response_model=ChangeApprovalRequestRead)
def approve(
    request_id: str,
    session: DatabaseSession,
    principal: Authenticated,
) -> ChangeApprovalRequestRead:
    _require_human(principal)
    request = _request_or_404(session, request_id)
    change = TypeAdapter(ChangePreviewCreate).validate_python(request.change)
    preview = ChangePreviewRead.model_validate(request.preview)
    approve_request(
        session,
        request,
        change=change,
        preview=preview,
        principal=principal,
    )
    return approval_request_read(session, request, principal)


@router.post("/{request_id}/reject", response_model=ChangeApprovalRequestRead)
def reject(
    request_id: str,
    session: DatabaseSession,
    principal: Authenticated,
) -> ChangeApprovalRequestRead:
    _require_human(principal)
    request = reject_request(
        session,
        _request_or_404(session, request_id),
        principal=principal,
    )
    return approval_request_read(session, request, principal)


def _request_or_404(
    session: DatabaseSession,
    request_id: str,
) -> ChangeApprovalRequest:
    request = session.get(ChangeApprovalRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return request


def _require_human(principal: Authenticated) -> None:
    if principal.authentication_method == "human_session":
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Approval decisions require a human session",
    )
