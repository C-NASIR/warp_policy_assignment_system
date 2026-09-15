from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.demo_seed import READ_ONLY_API_TOKEN, TEST_USERS, seed_demo_company
from app.models import (
    Employee,
    EmployeeAssignment,
    EmployeeOverride,
    ScheduledReconciliation,
    SecurityEvent,
)
from app.services.auth import authenticate_token
from app.services.human_auth import authenticate_human

REFERENCE_TIME = datetime(2026, 9, 6, tzinfo=UTC)


def test_demo_seed_populates_a_connected_company_and_authentication(db):
    summary = seed_demo_company(db, reference_time=REFERENCE_TIME)

    assert summary.employees == 25
    assert summary.users == 11
    assert summary.roles == 9
    assert summary.groups == 8
    assert summary.policies == 15
    assert summary.assignments > 450
    assert summary.audit_logs > 650

    # A second call recognizes the complete seed instead of duplicating it.
    second = seed_demo_company(db, reference_time=REFERENCE_TIME)
    assert second == summary

    active_specs = [
        spec for spec in TEST_USERS if spec.get("status", "active") == "active"
    ]
    for spec in active_specs:
        user, created_session = authenticate_human(
            db,
            email=spec["email"],
            password=spec["password"],
            client_ip="127.0.0.1",
            user_agent="seed-test",
        )
        assert user.name == spec["name"]
        created_session.record.revoked_at = REFERENCE_TIME

    principal = authenticate_token(db, READ_ONLY_API_TOKEN)
    assert principal.subject == "cedar-harbor-bi"
    assert principal.scopes == frozenset({"read", "audit"})

    assert (
        db.scalar(
            select(func.count())
            .select_from(EmployeeAssignment)
            .where(EmployeeAssignment.effective_until.is_not(None))
        )
        > 100
    )
    assert db.scalar(select(func.count()).select_from(EmployeeOverride)) == 5
    assert db.scalar(select(func.count()).select_from(SecurityEvent)) >= 7
    assert (
        db.scalar(
            select(func.count())
            .select_from(ScheduledReconciliation)
            .where(ScheduledReconciliation.status == "pending")
        )
        > 0
    )


def test_demo_seed_refuses_to_merge_with_existing_tenant_data(db):
    db.add(
        Employee(
            name="Existing Employee",
            state="IL",
            department="Operations",
            employee_type="Full-time",
            location="Chicago",
            start_date=REFERENCE_TIME.date(),
        )
    )
    db.flush()

    with pytest.raises(RuntimeError, match="fresh testing database"):
        seed_demo_company(db, reference_time=REFERENCE_TIME)
