import hmac
import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

DatabaseSession = Annotated[Session, Depends(get_db)]


def get_audit_actor(x_actor: Annotated[str | None, Header()] = None) -> str:
    """Identify an API mutation until the application gains full authentication."""
    actor = (x_actor or "api").strip()
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Actor cannot be blank",
        )
    if len(actor) > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Actor cannot exceed 200 characters",
        )
    return actor


AuditActor = Annotated[str, Depends(get_audit_actor)]


def require_audit_reader(x_audit_key: Annotated[str | None, Header()] = None) -> None:
    expected_key = os.getenv("AUDIT_ADMIN_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit-log read access is not configured",
        )
    if x_audit_key is None or not hmac.compare_digest(x_audit_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Audit-log read access denied",
        )


AuditReader = Annotated[None, Depends(require_audit_reader)]
