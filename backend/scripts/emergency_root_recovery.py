"""Offline, audited Root recovery for use from a trusted application host."""

from __future__ import annotations

import argparse
import getpass
import hmac
import os
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.dates import current_datetime
from app.models import AuthSession, User
from app.services.audit import record_audit_log
from app.services.human_auth import hash_password, record_security_event


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover a PolicyOS Root account")
    parser.add_argument("email", help="Email address of the existing Root user")
    args = parser.parse_args()

    configured_key = os.getenv("AUTH_ROOT_RECOVERY_KEY", "")
    if len(configured_key.encode("utf-8")) < 32:
        print("AUTH_ROOT_RECOVERY_KEY must contain at least 32 bytes", file=sys.stderr)
        return 2
    supplied_key = getpass.getpass("Root recovery key: ")
    if not hmac.compare_digest(configured_key, supplied_key):
        print("Root recovery key rejected", file=sys.stderr)
        return 3
    password = getpass.getpass("New Root password (12+ characters): ")
    confirmation = getpass.getpass("Confirm new Root password: ")
    if password != confirmation or not 12 <= len(password) <= 128:
        print("Passwords must match and contain 12 to 128 characters", file=sys.stderr)
        return 4

    with SessionLocal.begin() as session:
        user = session.scalar(
            select(User).where(
                User.email == args.email.strip().casefold(), User.is_root.is_(True)
            )
        )
        if user is None:
            print("That Root account does not exist", file=sys.stderr)
            return 5
        now = current_datetime()
        session.query(AuthSession).filter(
            AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
        ).update({AuthSession.revoked_at: now})
        user.password_hash = hash_password(password)
        user.password_change_required = False
        user.password_changed_at = now
        user.mfa_enabled = False
        user.mfa_secret_ciphertext = None
        user.mfa_recovery_code_hashes = []
        record_security_event(
            session,
            user=user,
            event_type="emergency_root_recovery",
            severity="critical",
            details={"sessions_revoked": True, "mfa_reset": True},
        )
        record_audit_log(
            session,
            actor="emergency-root-recovery",
            entity_type="User",
            entity_id=user.id,
            action="emergency_root_recovery",
            before=None,
            after={"sessions_revoked": True, "mfa_reset": True},
        )
    print("Root credentials recovered. Sign in and enroll MFA immediately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
