from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from app.dates import current_datetime, ensure_utc
from app.models import AuthSession, User
from app.services.audit import record_audit_log, snapshot_entity
from app.services.auth import AuthenticationError

SESSION_COOKIE_NAME = "policyos_session"
DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60
_ROOT_SETUP_LOCK_ID = 762341909
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("policyos-dummy-password-value")


@dataclass(frozen=True)
class CreatedSession:
    token: str
    record: AuthSession


def root_setup_required(session: Session) -> bool:
    return (session.scalar(select(func.count(User.id))) or 0) == 0


def create_root_user(
    session: Session,
    *,
    name: str,
    email: str,
    password: str,
) -> tuple[User, CreatedSession]:
    session.execute(text(f"SELECT pg_advisory_xact_lock({_ROOT_SETUP_LOCK_ID})"))
    if not root_setup_required(session):
        raise ValueError("Root setup has already been completed")

    user = User(
        name=name.strip(),
        email=normalize_email(email),
        password_hash=hash_password(password),
        status="active",
        is_root=True,
        password_change_required=False,
    )
    session.add(user)
    session.flush()
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="root_created",
        before=None,
        after=snapshot_entity(user, exclude={"password_hash"}),
    )
    return user, create_session(session, user)


def authenticate_human(
    session: Session,
    *,
    email: str,
    password: str,
) -> tuple[User, CreatedSession]:
    normalized = normalize_email(email)
    user = session.scalar(select(User).where(User.email == normalized))
    candidate_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    if not verify_password(candidate_hash, password) or user is None or user.status != "active":
        raise AuthenticationError(
            "Email or password is incorrect",
            code="invalid_login",
        )

    if _PASSWORD_HASHER.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = current_datetime()
    created = create_session(session, user)
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="logged_in",
        before=None,
        after={"session_id": created.record.id},
    )
    return user, created


def create_session(session: Session, user: User) -> CreatedSession:
    token = f"pos_{secrets.token_urlsafe(48)}"
    now = current_datetime()
    record = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        created_at=now,
        expires_at=now + timedelta(seconds=session_ttl_seconds()),
        last_seen_at=now,
    )
    session.add(record)
    session.flush()
    return CreatedSession(token=token, record=record)


def authenticate_session(session: Session, token: str) -> tuple[User, AuthSession]:
    record = session.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_session_token(token))
    )
    now = current_datetime()
    if record is None:
        raise AuthenticationError("The user session is invalid", code="invalid_session")
    if record.revoked_at is not None:
        raise AuthenticationError("The user session has ended", code="session_revoked")
    if now >= ensure_utc(record.expires_at):
        record.revoked_at = now
        raise AuthenticationError("The user session has expired", code="session_expired")
    if record.user.status != "active":
        raise AuthenticationError("The user account is not active", code="account_inactive")
    if now - ensure_utc(record.last_seen_at) >= timedelta(minutes=5):
        record.last_seen_at = now
    return record.user, record


def revoke_session(session: Session, record: AuthSession) -> None:
    if record.revoked_at is None:
        record.revoked_at = current_datetime()
        record_audit_log(
            session,
            actor=record.user.email,
            entity_type="User",
            entity_id=record.user_id,
            action="logged_out",
            before={"session_id": record.id},
            after=None,
        )


def change_password(
    session: Session,
    *,
    user: User,
    current_session: AuthSession,
    current_password: str,
    new_password: str,
) -> CreatedSession:
    if not verify_password(user.password_hash, current_password):
        raise AuthenticationError(
            "Current password is incorrect",
            code="invalid_current_password",
        )
    if verify_password(user.password_hash, new_password):
        raise ValueError("The new password must be different from the current password")

    now = current_datetime()
    user.password_hash = hash_password(new_password)
    user.password_change_required = False
    active_sessions = session.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
    )
    for record in active_sessions:
        record.revoked_at = now
    session.flush()
    replacement = create_session(session, user)
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="password_changed",
        before={"session_id": current_session.id},
        after={"session_id": replacement.record.id},
    )
    return replacement


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def session_ttl_seconds() -> int:
    raw = os.getenv("AUTH_SESSION_TTL_SECONDS", str(DEFAULT_SESSION_TTL_SECONDS))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("AUTH_SESSION_TTL_SECONDS must be an integer") from exc
    if not 300 <= value <= 30 * 24 * 60 * 60:
        raise RuntimeError("AUTH_SESSION_TTL_SECONDS must be between 300 and 2592000")
    return value


def session_cookie_secure() -> bool:
    value = os.getenv("AUTH_SESSION_COOKIE_SECURE", "false").strip().casefold()
    if value not in {"true", "false"}:
        raise RuntimeError("AUTH_SESSION_COOKIE_SECURE must be true or false")
    return value == "true"
