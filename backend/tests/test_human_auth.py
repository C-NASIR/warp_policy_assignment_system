from sqlalchemy import select

from app.models import AuthSession, User
from app.services.human_auth import SESSION_COOKIE_NAME, hash_session_token


ROOT = {
    "name": "Priya Shah",
    "email": "Priya.Shah@example.com",
    "password": "correct horse battery staple",
}


def _use_human_auth(client) -> None:
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"


def _setup_root(client) -> dict:
    response = client.post("/auth/setup-root", json=ROOT)
    assert response.status_code == 201, response.text
    return response.json()


def test_root_setup_is_one_time_and_starts_a_human_session(client, db):
    assert client.get("/auth/setup-status").json() == {"setup_required": True}

    user = _setup_root(client)
    assert user["email"] == "priya.shah@example.com"
    assert user["name"] == "Priya Shah"
    assert user["is_root"] is True
    assert user["status"] == "active"
    assert "password" not in user
    assert "HttpOnly" in client.post("/auth/login", json={
        "email": ROOT["email"],
        "password": ROOT["password"],
    }).headers["set-cookie"]

    stored = db.scalar(select(User).where(User.email == "priya.shah@example.com"))
    assert stored is not None
    assert stored.password_hash != ROOT["password"]
    assert stored.password_hash.startswith("$argon2id$")

    assert client.get("/auth/setup-status").json() == {"setup_required": False}
    duplicate = client.post("/auth/setup-root", json=ROOT)
    assert duplicate.status_code == 409
    assert "already been completed" in duplicate.json()["error"]["message"]


def test_human_session_authenticates_business_requests_and_logout_revokes_it(client):
    _setup_root(client)
    _use_human_auth(client)

    current = client.get("/auth/me")
    assert current.status_code == 200
    assert current.json()["email"] == "priya.shah@example.com"
    assert client.get("/employees").status_code == 200

    logout = client.post("/auth/logout")
    assert logout.status_code == 204
    assert SESSION_COOKIE_NAME not in client.cookies
    denied = client.get("/employees")
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "authentication_required"


def test_login_and_password_change_rotate_the_session(client):
    _setup_root(client)
    _use_human_auth(client)
    assert client.post("/auth/logout").status_code == 204

    invalid = client.post(
        "/auth/login",
        json={"email": ROOT["email"], "password": "not-the-password"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "invalid_login"

    login = client.post(
        "/auth/login",
        json={"email": ROOT["email"], "password": ROOT["password"]},
    )
    assert login.status_code == 200
    previous_token = client.cookies.get(SESSION_COOKIE_NAME)

    wrong_current = client.post(
        "/auth/change-password",
        json={
            "current_password": "wrong-current-password",
            "new_password": "a completely different password",
        },
    )
    assert wrong_current.status_code == 401
    assert wrong_current.json()["error"]["code"] == "invalid_current_password"

    changed = client.post(
        "/auth/change-password",
        json={
            "current_password": ROOT["password"],
            "new_password": "a completely different password",
        },
    )
    assert changed.status_code == 200
    assert client.cookies.get(SESSION_COOKIE_NAME) != previous_token

    assert client.post("/auth/logout").status_code == 204
    old_password = client.post(
        "/auth/login",
        json={"email": ROOT["email"], "password": ROOT["password"]},
    )
    assert old_password.status_code == 401
    new_password = client.post(
        "/auth/login",
        json={
            "email": ROOT["email"],
            "password": "a completely different password",
        },
    )
    assert new_password.status_code == 200


def test_session_tokens_are_stored_only_as_hashes(client, db):
    _setup_root(client)
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token is not None

    stored = db.scalar(select(AuthSession).where(AuthSession.revoked_at.is_(None)))
    assert stored is not None
    assert stored.token_hash == hash_session_token(token)
    assert stored.token_hash != token

    user_audits = client.get(
        "/audit-logs",
        params={"entity_type": "User"},
    ).json()
    assert user_audits[0]["action"] == "root_created"
    assert "password_hash" not in str(user_audits)


def test_human_session_rejects_untrusted_state_changes(client):
    _setup_root(client)
    _use_human_auth(client)

    denied = client.post(
        "/employees",
        headers={"Origin": "https://untrusted.example"},
        json={
            "name": "Avery Stone",
            "state": "Illinois",
            "department": "Operations",
            "employee_type": "full-time",
        },
    )
    assert denied.status_code == 403
    assert "trusted origin" in denied.json()["detail"]
