from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified

from app.dates import current_datetime, ensure_utc
from app.models import (
    AuthSession,
    LoginThrottle,
    PasswordResetToken,
    SecurityEvent,
    User,
)
from app.services.audit import record_audit_log, snapshot_entity
from app.services.auth import AuthenticationError

SESSION_COOKIE_NAME = "policyos_session"
DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60
DEFAULT_SESSION_IDLE_TTL_SECONDS = 30 * 60
DEFAULT_REAUTH_TTL_SECONDS = 10 * 60
_ROOT_SETUP_LOCK_ID = 762341909
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16
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
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, CreatedSession]:
    session.execute(text(f"SELECT pg_advisory_xact_lock({_ROOT_SETUP_LOCK_ID})"))
    if not root_setup_required(session):
        raise ValueError("Root setup has already been completed")
    now = current_datetime()
    user = User(
        name=name.strip(),
        email=normalize_email(email),
        password_hash=hash_password(password),
        status="active",
        is_root=True,
        password_change_required=False,
        password_changed_at=now,
        last_login_at=now,
    )
    session.add(user)
    session.flush()
    record_security_event(
        session,
        user=user,
        event_type="root_account_created",
        severity="critical",
        details={"ip": client_ip},
    )
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="root_created",
        before=None,
        after=snapshot_entity(
            user,
            exclude={
                "password_hash",
                "mfa_secret_ciphertext",
                "mfa_recovery_code_hashes",
            },
        ),
    )
    return user, create_session(
        session, user, client_ip=client_ip, user_agent=user_agent
    )


def authenticate_human(
    session: Session,
    *,
    email: str,
    password: str,
    mfa_code: str | None = None,
    recovery_code: str | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, CreatedSession]:
    normalized = normalize_email(email)
    throttle_key = _throttle_key(normalized, client_ip)
    _assert_login_not_throttled(session, throttle_key)
    user = session.scalar(select(User).where(User.email == normalized))
    candidate_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    if (
        not verify_password(candidate_hash, password)
        or user is None
        or user.status != "active"
    ):
        _record_login_failure(session, throttle_key, user=user, client_ip=client_ip)
        raise AuthenticationError(
            "Email or password is incorrect", code="invalid_login"
        )
    if user.mfa_enabled:
        if not mfa_code and not recovery_code:
            raise AuthenticationError(
                "A verification code is required",
                code="mfa_required",
                metadata={"methods": ["totp", "recovery_code"]},
            )
        if not verify_user_factor(
            user, mfa_code=mfa_code, recovery_code=recovery_code, consume_recovery=True
        ):
            _record_login_failure(session, throttle_key, user=user, client_ip=client_ip)
            raise AuthenticationError(
                "The verification code is invalid", code="invalid_mfa_code"
            )

    session.execute(delete(LoginThrottle).where(LoginThrottle.key_hash == throttle_key))
    if _PASSWORD_HASHER.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    now = current_datetime()
    user.last_login_at = now
    previous_context = session.execute(
        select(AuthSession.created_ip, AuthSession.user_agent)
        .where(AuthSession.user_id == user.id)
        .order_by(AuthSession.created_at.desc())
        .limit(1)
    ).one_or_none()
    created = create_session(
        session,
        user,
        client_ip=client_ip,
        user_agent=user_agent,
        mfa_verified=user.mfa_enabled,
    )
    previous_ip = previous_context[0] if previous_context else None
    previous_user_agent = previous_context[1] if previous_context else None
    new_ip = bool(
        client_ip and previous_ip and not hmac.compare_digest(client_ip, previous_ip)
    )
    new_user_agent = bool(
        user_agent
        and previous_user_agent
        and not hmac.compare_digest(user_agent[:500], previous_user_agent)
    )
    if new_ip or new_user_agent:
        record_security_event(
            session,
            user=user,
            event_type="login_from_new_context",
            severity="warning",
            details={
                "ip": client_ip,
                "previous_ip": previous_ip,
                "new_address": new_ip,
                "new_device": new_user_agent,
            },
        )
    record_security_event(
        session,
        user=user,
        event_type="login_succeeded",
        details={"session_id": created.record.id, "ip": client_ip},
    )
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="logged_in",
        before=None,
        after={"session_id": created.record.id, "mfa_verified": user.mfa_enabled},
    )
    return user, created


def create_session(
    session: Session,
    user: User,
    *,
    client_ip: str | None = None,
    user_agent: str | None = None,
    mfa_verified: bool = False,
) -> CreatedSession:
    token = f"pos_{secrets.token_urlsafe(48)}"
    now = current_datetime()
    record = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        created_at=now,
        expires_at=now + timedelta(seconds=session_ttl_seconds()),
        last_seen_at=now,
        reauthenticated_at=now,
        mfa_verified_at=now if mfa_verified else None,
        created_ip=client_ip,
        last_ip=client_ip,
        user_agent=(user_agent or "")[:500] or None,
    )
    session.add(record)
    session.flush()
    return CreatedSession(token=token, record=record)


def authenticate_session(
    session: Session, token: str, *, client_ip: str | None = None
) -> tuple[User, AuthSession]:
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
        raise AuthenticationError(
            "The user session has expired", code="session_expired"
        )
    if now - ensure_utc(record.last_seen_at) >= timedelta(
        seconds=session_idle_ttl_seconds()
    ):
        record.revoked_at = now
        raise AuthenticationError(
            "The user session expired after being idle", code="session_idle_expired"
        )
    if record.user.status != "active":
        raise AuthenticationError(
            "The user account is not active", code="account_inactive"
        )
    if now - ensure_utc(record.last_seen_at) >= timedelta(seconds=60):
        record.last_seen_at = now
    if client_ip:
        record.last_ip = client_ip
    return record.user, record


def revoke_session(session: Session, record: AuthSession) -> None:
    if record.revoked_at is None:
        record.revoked_at = current_datetime()
        record_security_event(
            session,
            user=record.user,
            event_type="session_signed_out",
            details={"session_id": record.id},
        )
        record_audit_log(
            session,
            actor=record.user.email,
            entity_type="User",
            entity_id=record.user_id,
            action="logged_out",
            before={"session_id": record.id},
            after=None,
        )


def revoke_user_sessions(
    session: Session,
    *,
    user: User,
    current_session_id: int | None = None,
    include_current: bool,
) -> int:
    records = list(
        session.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
            )
        )
    )
    now = current_datetime()
    revoked = 0
    for record in records:
        if not include_current and record.id == current_session_id:
            continue
        record.revoked_at = now
        revoked += 1
    record_security_event(
        session,
        user=user,
        event_type="sessions_revoked",
        severity="warning" if include_current else "info",
        details={"count": revoked, "included_current": include_current},
    )
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="sessions_revoked",
        before=None,
        after={"count": revoked, "included_current": include_current},
    )
    return revoked


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
            "Current password is incorrect", code="invalid_current_password"
        )
    if verify_password(user.password_hash, new_password):
        raise ValueError("The new password must be different from the current password")
    user.password_hash = hash_password(new_password)
    user.password_change_required = False
    user.password_changed_at = current_datetime()
    revoke_user_sessions(session, user=user, include_current=True)
    session.flush()
    replacement = create_session(
        session,
        user,
        client_ip=current_session.last_ip,
        user_agent=current_session.user_agent,
        mfa_verified=user.mfa_enabled,
    )
    record_security_event(
        session,
        user=user,
        event_type="password_changed",
        severity="warning",
        details={"session_id": replacement.record.id},
    )
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


def begin_mfa_setup(
    session: Session,
    *,
    user: User,
    current_session: AuthSession,
    current_password: str,
) -> tuple[str, str]:
    if user.mfa_enabled:
        raise ValueError(
            "Disable the current MFA method before enrolling a replacement"
        )
    if not verify_password(user.password_hash, current_password):
        raise AuthenticationError(
            "Current password is incorrect", code="invalid_current_password"
        )
    secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    current_session.pending_mfa_secret_ciphertext = encrypt_mfa_secret(secret)
    issuer = quote(os.getenv("AUTH_MFA_ISSUER", "PolicyOS"), safe="")
    account = quote(user.email, safe="")
    uri = f"otpauth://totp/{issuer}:{account}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    record_security_event(session, user=user, event_type="mfa_enrollment_started")
    return secret, uri


def confirm_mfa_setup(
    session: Session,
    *,
    user: User,
    current_session: AuthSession,
    code: str,
) -> list[str]:
    encrypted = current_session.pending_mfa_secret_ciphertext
    if not encrypted:
        raise ValueError("Start MFA setup before confirming a code")
    secret = decrypt_mfa_secret(encrypted)
    if not verify_totp(secret, code):
        raise AuthenticationError(
            "The verification code is invalid", code="invalid_mfa_code"
        )
    codes = generate_recovery_codes()
    user.mfa_enabled = True
    user.mfa_secret_ciphertext = encrypted
    user.mfa_recovery_code_hashes = [
        hash_password(normalize_recovery_code(value)) for value in codes
    ]
    current_session.pending_mfa_secret_ciphertext = None
    now = current_datetime()
    current_session.mfa_verified_at = now
    current_session.reauthenticated_at = now
    record_security_event(
        session, user=user, event_type="mfa_enabled", severity="warning"
    )
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="mfa_enabled",
        before={"mfa_enabled": False},
        after={"mfa_enabled": True},
    )
    return codes


def disable_mfa(
    session: Session,
    *,
    user: User,
    current_session: AuthSession,
    current_password: str,
    mfa_code: str | None,
    recovery_code: str | None,
) -> CreatedSession:
    if not verify_password(user.password_hash, current_password):
        raise AuthenticationError(
            "Current password is incorrect", code="invalid_current_password"
        )
    if not user.mfa_enabled:
        raise ValueError("MFA is not enabled")
    if not verify_user_factor(
        user, mfa_code=mfa_code, recovery_code=recovery_code, consume_recovery=True
    ):
        raise AuthenticationError(
            "The verification code is invalid", code="invalid_mfa_code"
        )
    user.mfa_enabled = False
    user.mfa_secret_ciphertext = None
    user.mfa_recovery_code_hashes = []
    revoke_user_sessions(session, user=user, include_current=True)
    replacement = create_session(
        session,
        user,
        client_ip=current_session.last_ip,
        user_agent=current_session.user_agent,
    )
    record_security_event(
        session, user=user, event_type="mfa_disabled", severity="critical"
    )
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="mfa_disabled",
        before={"mfa_enabled": True},
        after={"mfa_enabled": False},
    )
    return replacement


def reauthenticate(
    session: Session,
    *,
    user: User,
    current_session: AuthSession,
    password: str,
    mfa_code: str | None,
    recovery_code: str | None,
) -> CreatedSession:
    if not verify_password(user.password_hash, password):
        raise AuthenticationError(
            "Password is incorrect", code="invalid_current_password"
        )
    if user.mfa_enabled and not verify_user_factor(
        user,
        mfa_code=mfa_code,
        recovery_code=recovery_code,
        consume_recovery=True,
    ):
        raise AuthenticationError(
            "A valid verification code is required", code="invalid_mfa_code"
        )
    current_session.revoked_at = current_datetime()
    replacement = create_session(
        session,
        user,
        client_ip=current_session.last_ip,
        user_agent=current_session.user_agent,
        mfa_verified=user.mfa_enabled,
    )
    record_security_event(
        session,
        user=user,
        event_type="sensitive_action_reauthenticated",
        details={"session_id": replacement.record.id},
    )
    return replacement


def request_password_reset(
    session: Session, *, email: str, client_ip: str | None
) -> str | None:
    user = session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or user.status != "active":
        return None
    now = current_datetime()
    session.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        )
    )
    token = f"prst_{secrets.token_urlsafe(48)}"
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_session_token(token),
            created_at=now,
            expires_at=now + timedelta(minutes=30),
            requested_ip=client_ip,
        )
    )
    record_security_event(
        session,
        user=user,
        event_type="password_reset_requested",
        severity="warning",
        details={"ip": client_ip},
    )
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="password_reset_requested",
        before=None,
        after={"ip": client_ip},
    )
    return token


def confirm_password_reset(
    session: Session,
    *,
    token: str,
    new_password: str,
    mfa_code: str | None,
    recovery_code: str | None,
) -> User:
    record = session.scalar(
        select(PasswordResetToken)
        .options(joinedload(PasswordResetToken.user))
        .where(PasswordResetToken.token_hash == hash_session_token(token))
    )
    now = current_datetime()
    if (
        record is None
        or record.used_at is not None
        or now >= ensure_utc(record.expires_at)
    ):
        raise AuthenticationError(
            "The password reset link is invalid or expired", code="invalid_reset_token"
        )
    user = record.user
    if user.status != "active":
        raise AuthenticationError(
            "The user account is not active", code="account_inactive"
        )
    if user.mfa_enabled and not verify_user_factor(
        user,
        mfa_code=mfa_code,
        recovery_code=recovery_code,
        consume_recovery=True,
    ):
        raise AuthenticationError(
            "A valid verification or recovery code is required",
            code="mfa_required",
        )
    if verify_password(user.password_hash, new_password):
        raise ValueError("The new password must be different from the current password")
    user.password_hash = hash_password(new_password)
    user.password_change_required = False
    user.password_changed_at = now
    record.used_at = now
    revoke_user_sessions(session, user=user, include_current=True)
    record_security_event(
        session, user=user, event_type="password_reset_completed", severity="critical"
    )
    record_audit_log(
        session,
        actor=user.email,
        entity_type="User",
        entity_id=user.id,
        action="password_reset_completed",
        before=None,
        after={"sessions_revoked": True},
    )
    return user


def verify_user_factor(
    user: User,
    *,
    mfa_code: str | None,
    recovery_code: str | None,
    consume_recovery: bool,
) -> bool:
    if mfa_code and user.mfa_secret_ciphertext:
        try:
            return verify_totp(decrypt_mfa_secret(user.mfa_secret_ciphertext), mfa_code)
        except RuntimeError:
            return False
    if recovery_code:
        normalized = normalize_recovery_code(recovery_code)
        hashes = list(user.mfa_recovery_code_hashes or [])
        for index, code_hash in enumerate(hashes):
            if verify_password(code_hash, normalized):
                if consume_recovery:
                    hashes.pop(index)
                    user.mfa_recovery_code_hashes = hashes
                    flag_modified(user, "mfa_recovery_code_hashes")
                return True
    return False


def encrypt_mfa_secret(secret: str) -> str:
    return _mfa_fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_mfa_secret(ciphertext: str) -> str:
    try:
        return _mfa_fernet().decrypt(ciphertext.encode("ascii")).decode("ascii")
    except InvalidToken as exc:
        raise RuntimeError("The MFA encryption key is invalid or has changed") from exc


def _mfa_fernet() -> Fernet:
    raw = os.getenv("AUTH_MFA_ENCRYPTION_KEY", "")
    if len(raw.encode("utf-8")) < 32:
        raise RuntimeError("AUTH_MFA_ENCRYPTION_KEY must contain at least 32 bytes")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
    return Fernet(key)


def totp_code(secret: str, *, timestamp: int | None = None) -> str:
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    counter = int(timestamp if timestamp is not None else time.time()) // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (
        struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    ) % 1_000_000
    return f"{value:06d}"


def verify_totp(secret: str, code: str) -> bool:
    normalized = "".join(character for character in code if character.isdigit())
    if len(normalized) != 6:
        return False
    now = int(time.time())
    return any(
        hmac.compare_digest(totp_code(secret, timestamp=now + offset * 30), normalized)
        for offset in (-1, 0, 1)
    )


def generate_recovery_codes() -> list[str]:
    return [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(10)]


def normalize_recovery_code(value: str) -> str:
    return value.strip().casefold().replace(" ", "")


def record_security_event(
    session: Session,
    *,
    user: User,
    event_type: str,
    severity: str = "info",
    details: dict | None = None,
) -> SecurityEvent:
    event = SecurityEvent(
        user_id=user.id,
        event_type=event_type,
        severity=severity,
        details={
            key: value for key, value in (details or {}).items() if value is not None
        },
    )
    session.add(event)
    return event


def acknowledge_security_event(
    session: Session, *, user: User, event_id: int
) -> SecurityEvent:
    event = session.scalar(
        select(SecurityEvent).where(
            SecurityEvent.id == event_id, SecurityEvent.user_id == user.id
        )
    )
    if event is None:
        raise LookupError("Security event was not found")
    if event.acknowledged_at is None:
        event.acknowledged_at = current_datetime()
    return event


def privileged_mfa_required() -> bool:
    return _boolean_setting("AUTH_REQUIRE_PRIVILEGED_MFA", True)


def password_reset_token_exposed() -> bool:
    return _boolean_setting("AUTH_PASSWORD_RESET_EXPOSE_TOKEN", False)


def session_recently_reauthenticated(record: AuthSession) -> bool:
    return current_datetime() - ensure_utc(record.reauthenticated_at) < timedelta(
        seconds=reauth_ttl_seconds()
    )


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
    return _integer_setting(
        "AUTH_SESSION_TTL_SECONDS", DEFAULT_SESSION_TTL_SECONDS, 300, 30 * 24 * 60 * 60
    )


def session_idle_ttl_seconds() -> int:
    return _integer_setting(
        "AUTH_SESSION_IDLE_TTL_SECONDS",
        DEFAULT_SESSION_IDLE_TTL_SECONDS,
        60,
        24 * 60 * 60,
    )


def reauth_ttl_seconds() -> int:
    return _integer_setting(
        "AUTH_REAUTH_TTL_SECONDS", DEFAULT_REAUTH_TTL_SECONDS, 60, 60 * 60
    )


def session_cookie_secure() -> bool:
    return _boolean_setting("AUTH_SESSION_COOKIE_SECURE", False)


def _integer_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


def _boolean_setting(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default).lower()).strip().casefold()
    if raw not in {"true", "false"}:
        raise RuntimeError(f"{name} must be true or false")
    return raw == "true"


def _throttle_key(email: str, client_ip: str | None) -> str:
    return hashlib.sha256(f"{email}|{client_ip or 'unknown'}".encode()).hexdigest()


def _assert_login_not_throttled(session: Session, key_hash: str) -> None:
    # Serialize attempts for one normalized account/IP pair so concurrent
    # requests cannot evade counters or race the first insert.
    lock_id = int.from_bytes(bytes.fromhex(key_hash[:16]), signed=True)
    session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
    )
    record = session.get(LoginThrottle, key_hash)
    now = current_datetime()
    if record and record.locked_until and now < ensure_utc(record.locked_until):
        retry_after = max(
            1, int((ensure_utc(record.locked_until) - now).total_seconds())
        )
        raise AuthenticationError(
            "Too many sign-in attempts. Try again later",
            code="login_throttled",
            metadata={"retry_after_seconds": retry_after},
        )


def _record_login_failure(
    session: Session,
    key_hash: str,
    *,
    user: User | None,
    client_ip: str | None,
) -> None:
    now = current_datetime()
    window = timedelta(minutes=15)
    record = session.get(LoginThrottle, key_hash)
    if record is None:
        record = LoginThrottle(key_hash=key_hash, failed_count=0, window_started_at=now)
        session.add(record)
    elif now - ensure_utc(record.window_started_at) >= window:
        record.failed_count = 0
        record.window_started_at = now
        record.locked_until = None
    record.failed_count += 1
    record.updated_at = now
    if record.failed_count >= 5:
        record.locked_until = now + timedelta(minutes=15)
    if user is not None:
        record_security_event(
            session,
            user=user,
            event_type="login_failed",
            severity="warning" if record.failed_count >= 3 else "info",
            details={
                "ip": client_ip,
                "attempts": record.failed_count,
                "locked": bool(record.locked_until),
            },
        )
