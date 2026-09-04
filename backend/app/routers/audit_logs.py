from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.dependencies import DatabaseSession, EmployeeScope
from app.models import AuditLog
from app.pagination import Pagination, paginate_scalars
from app.schemas import AuditLogRead
from app.services.audit import audit_log_statement
from app.services.employee_visibility import apply_audit_visibility

router = APIRouter(prefix="/audit-logs", tags=["audit logs"])


@router.get("", response_model=list[AuditLogRead])
def list_all(
    session: DatabaseSession,
    response: Response,
    pagination: Pagination,
    visibility: EmployeeScope,
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor: str | None = None,
    action: str | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> list[AuditLog]:
    statement = audit_log_statement(
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        action=action,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        search=search,
    )
    statement = apply_audit_visibility(statement, visibility)
    return paginate_scalars(
        session,
        statement.order_by(AuditLog.timestamp, AuditLog.id),
        pagination,
        response,
    )
