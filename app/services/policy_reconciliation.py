from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dates import current_datetime, ensure_utc
from app.models import Employee, Policy
from app.services.policy_matching import refresh_employee_policies
from app.services.reconciliation import refresh_employee_assignments


def refresh_employees_affected_by_policy(
    session: Session,
    policy: Policy,
    reconciliation_at: datetime | None = None,
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
    evaluation_date = reconciliation_at.date()
    employees = list(session.scalars(select(Employee).order_by(Employee.id)))

    for employee in employees:
        refresh_employee_policies(session, employee.id, evaluation_date)
        refresh_employee_assignments(
            session,
            employee,
            evaluation_date,
            reconciliation_at,
        )
