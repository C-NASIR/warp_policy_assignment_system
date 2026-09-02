from datetime import datetime

from fastapi import APIRouter, Query

from app.dependencies import DatabaseSession
from app.models import AuditLog
from app.schemas import AuditLogRead
from app.services.audit import list_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["audit logs"])


@router.get("", response_model=list[AuditLogRead])
def list_all(
    session: DatabaseSession,
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor: str | None = None,
    action: str | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLog]:
    return list_audit_logs(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        action=action,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        limit=limit,
        offset=offset,
    )
