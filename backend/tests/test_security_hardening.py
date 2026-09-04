from datetime import timedelta

from sqlalchemy import func, select

from app.dates import current_datetime
from app.models import (
    AuthSession,
    LoginThrottle,
    PasswordResetToken,
    SecurityEvent,
    User,
)
from app.services.human_auth import SESSION_COOKIE_NAME, hash_session_token, totp_code

ROOT = {
    "name": "Security Root",
    "email": "security@example.com",
    "password": "correct horse battery staple",
}


def _human(client):
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"


def _setup(client):
    response = client.post("/auth/setup-root", json=ROOT)
    assert response.status_code == 201, response.text
    _human(client)


def _enroll_mfa(client) -> tuple[str, list[str]]:
    started = client.post(
        "/auth/mfa/setup", json={"current_password": ROOT["password"]}
    )
    assert started.status_code == 200, started.text
    secret = started.json()["secret"]
    confirmed = client.post("/auth/mfa/confirm", json={"code": totp_code(secret)})
    assert confirmed.status_code == 200, confirmed.text
    return secret, confirmed.json()["recovery_codes"]


def test_login_throttling_is_persistent_and_audited(client, db):
    _setup(client)
    assert client.post("/auth/logout").status_code == 204
    for _ in range(5):
        denied = client.post(
            "/auth/login",
            json={"email": ROOT["email"], "password": "wrong password"},
        )
        assert denied.status_code == 401

    throttled = client.post(
        "/auth/login", json={"email": ROOT["email"], "password": ROOT["password"]}
    )
    assert throttled.status_code == 429
    assert throttled.json()["error"]["code"] == "login_throttled"
    assert int(throttled.headers["retry-after"]) > 0
    assert db.scalar(select(func.count(LoginThrottle.key_hash))) == 1
    assert (
        db.scalar(
            select(func.count(SecurityEvent.id)).where(
                SecurityEvent.event_type == "login_failed"
            )
        )
        == 5
    )


def test_totp_and_one_time_recovery_codes_protect_login(client, db):
    _setup(client)
    secret, recovery_codes = _enroll_mfa(client)
    user = db.scalar(select(User).where(User.email == ROOT["email"]))
    assert user is not None and user.mfa_enabled
    assert user.mfa_secret_ciphertext != secret
    assert secret not in " ".join(user.mfa_recovery_code_hashes)

    assert client.post("/auth/logout").status_code == 204
    missing = client.post(
        "/auth/login", json={"email": ROOT["email"], "password": ROOT["password"]}
    )
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "mfa_required"
    assert (
        client.post(
            "/auth/login",
            headers={"User-Agent": "Phase7 new browser"},
            json={
                "email": ROOT["email"],
                "password": ROOT["password"],
                "mfa_code": totp_code(secret),
            },
        ).status_code
        == 200
    )
    assert (
        db.scalar(
            select(func.count(SecurityEvent.id)).where(
                SecurityEvent.event_type == "login_from_new_context"
            )
        )
        == 1
    )
    assert client.post("/auth/logout").status_code == 204

    recovery = recovery_codes[0]
    assert (
        client.post(
            "/auth/login",
            json={
                "email": ROOT["email"],
                "password": ROOT["password"],
                "recovery_code": recovery,
            },
        ).status_code
        == 200
    )
    assert client.post("/auth/logout").status_code == 204
    reused = client.post(
        "/auth/login",
        json={
            "email": ROOT["email"],
            "password": ROOT["password"],
            "recovery_code": recovery,
        },
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "invalid_mfa_code"


def test_password_recovery_is_generic_single_use_and_revokes_sessions(
    client, db, monkeypatch
):
    monkeypatch.setenv("AUTH_PASSWORD_RESET_EXPOSE_TOKEN", "true")
    _setup(client)
    old_token = client.cookies.get(SESSION_COOKIE_NAME)
    unknown = client.post(
        "/auth/password-reset/request", json={"email": "unknown@example.com"}
    )
    known = client.post("/auth/password-reset/request", json={"email": ROOT["email"]})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json()["message"] == known.json()["message"]
    assert unknown.json()["reset_token"] is None
    reset_token = known.json()["reset_token"]
    assert reset_token.startswith("prst_")
    stored = db.scalar(select(PasswordResetToken))
    assert stored is not None and stored.token_hash == hash_session_token(reset_token)

    changed = client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "a completely new password"},
    )
    assert changed.status_code == 204
    client.cookies.set(SESSION_COOKIE_NAME, old_token)
    assert client.get("/auth/me").status_code == 401
    reused = client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "another completely new password"},
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "invalid_reset_token"


def test_idle_expiration_and_sign_out_other_devices(client, db):
    _setup(client)
    first_token = client.cookies.get(SESSION_COOKIE_NAME)
    login = client.post(
        "/auth/login", json={"email": ROOT["email"], "password": ROOT["password"]}
    )
    assert login.status_code == 200
    second_token = client.cookies.get(SESSION_COOKIE_NAME)
    security = client.get("/auth/security").json()
    assert len(security["sessions"]) == 2
    assert sum(item["current"] for item in security["sessions"]) == 1
    assert client.post("/auth/sessions/revoke-others").status_code == 204
    first = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_session_token(first_token)
        )
    )
    assert first is not None and first.revoked_at is not None

    current = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_session_token(second_token)
        )
    )
    assert current is not None
    current.last_seen_at = current_datetime() - timedelta(hours=1)
    db.commit()
    expired = client.get("/auth/me")
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "session_idle_expired"


def test_privileged_mfa_and_recent_reauthentication_are_enforced(
    client, db, monkeypatch
):
    _setup(client)
    monkeypatch.setenv("AUTH_REQUIRE_PRIVILEGED_MFA", "true")
    role = {
        "name": "Reviewers",
        "permissions": ["access:read"],
        "employee_scope": "none",
        "assignment_field_scope": "none",
    }
    blocked = client.post("/roles", json=role)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "mfa_enrollment_required"

    secret, _ = _enroll_mfa(client)
    assert client.post("/roles", json=role).status_code == 201
    current = db.scalar(select(AuthSession).where(AuthSession.revoked_at.is_(None)))
    assert current is not None
    current.reauthenticated_at = current_datetime() - timedelta(hours=1)
    db.commit()
    stale = client.post("/roles", json={**role, "name": "Stale session role"})
    assert stale.status_code == 401
    assert stale.json()["error"]["code"] == "reauthentication_required"
    stepped_up = client.post(
        "/auth/reauthenticate",
        json={"password": ROOT["password"], "mfa_code": totp_code(secret)},
    )
    assert stepped_up.status_code == 200
    assert (
        client.post("/roles", json={**role, "name": "Fresh session role"}).status_code
        == 201
    )


def test_access_review_identifies_privileged_mfa_and_unused_role_risks(client):
    _setup(client)
    client.headers["Authorization"] = (
        "Bearer test-bootstrap-token-with-at-least-32-bytes"
    )
    client.headers.pop("Origin", None)
    created = client.post(
        "/roles",
        json={
            "name": "Unused broad role",
            "permissions": ["access:manage"],
            "employee_scope": "all",
            "assignment_field_scope": "all",
        },
    )
    assert created.status_code == 201
    review = client.get("/authorization/access-review")
    assert review.status_code == 200
    body = review.json()
    assert body["privileged_user_count"] == 1
    assert body["privileged_users_without_mfa"] == 1
    assert body["unused_role_count"] == 1
    assert {item["code"] for item in body["findings"]} >= {
        "privileged_user_without_mfa",
        "unused_role",
        "broad_data_scope",
        "privileged_role",
    }
