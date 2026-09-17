from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dates import current_datetime, ensure_utc
from app.models import Employee, Policy
from app.services.reconciliation import reconcile_employees


def refresh_employees_affected_by_policy(
    session: Session,
    policy: Policy,
    reconciliation_at: datetime | None = None,
    *,
    actor: str = "system",
) -> None:
    """Synchronously reconcile employees after a material policy change.

    A rule change can make any employee start or stop matching a policy. Until
    the system has a narrower impact index, every employee is therefore an
    affected candidate. Keeping the fan-out in the caller's session makes the
    policy mutation, audit rows, policy links, and assignment history atomic.
    """
    # Ensure pending policy/version changes are visible to the reconciliation
    # queries before beginning the fan-out.
    session.flush()
    reconciliation_at = ensure_utc(reconciliation_at or current_datetime())
    employee_ids = list(session.scalars(select(Employee.id).order_by(Employee.id)))
    reconcile_employees(
        session,
        employee_ids,
        reconciliation_at,
        actor=actor,
    )
