import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.browser_access import (
    BROWSER_EXPOSED_HEADERS,
    CORS_ALLOWED_ORIGINS_ENV,
    BrowserAccessConfigurationError,
    browser_allowed_origins,
    configure_browser_access,
    normalize_origins,
)
from app.main import app

ALLOWED_ORIGIN = "http://localhost:5173"
DISALLOWED_ORIGIN = "https://untrusted.example"


@pytest.fixture
def browser_client():
    browser_app = FastAPI()
    configure_browser_access(browser_app, allowed_origins=[ALLOWED_ORIGIN])

    @browser_app.get("/items")
    def list_items():
        return []

    with TestClient(browser_app) as client:
        yield client


def test_application_configures_local_react_origins_by_default():
    assert ALLOWED_ORIGIN in app.state.browser_allowed_origins
    assert "*" not in app.state.browser_allowed_origins


def test_allowed_preflight_needs_no_bearer_credential(browser_client):
    response = browser_client.options(
        "/items",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "authorization, content-type, x-actor"
            ),
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    allowed_headers = response.headers["Access-Control-Allow-Headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers
    assert "x-actor" in allowed_headers
    assert response.headers["Access-Control-Max-Age"] == "600"
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_allowed_response_exposes_frontend_metadata(browser_client):
    response = browser_client.get("/items", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
    exposed = {
        header.strip().lower()
        for header in response.headers["Access-Control-Expose-Headers"].split(",")
    }
    assert exposed == {header.lower() for header in BROWSER_EXPOSED_HEADERS}
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_protected_auth_error_is_readable_by_allowed_frontend(session_factory):
    client = TestClient(app)
    try:
        response = client.get(
            "/employees",
            headers={"Origin": ALLOWED_ORIGIN},
        )
    finally:
        client.close()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_disallowed_origin_receives_no_browser_access(browser_client):
    preflight = browser_client.options(
        "/items",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    response = browser_client.get(
        "/items",
        headers={"Origin": DISALLOWED_ORIGIN},
    )

    assert preflight.status_code == 400
    assert "Access-Control-Allow-Origin" not in preflight.headers
    # The server may process a non-preflight request, but the browser cannot
    # expose it to JavaScript without this response header.
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers


def test_environment_allowlist_is_normalized_and_deduplicated(monkeypatch):
    monkeypatch.setenv(
        CORS_ALLOWED_ORIGINS_ENV,
        " HTTPS://UI.Example.com:443/,http://localhost:4173,https://ui.example.com ",
    )

    assert browser_allowed_origins() == (
        "https://ui.example.com",
        "http://localhost:4173",
    )


def test_empty_environment_allowlist_disables_cross_origin_access(monkeypatch):
    monkeypatch.setenv(CORS_ALLOWED_ORIGINS_ENV, "  ")

    assert browser_allowed_origins() == ()


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "ui.example.com",
        "https://ui.example.com/app",
        "https://user@ui.example.com",
        "https://ui.example.com?tenant=1",
        "https://ui example.com",
    ],
)
def test_unsafe_or_malformed_origins_are_rejected(origin):
    with pytest.raises(BrowserAccessConfigurationError):
        normalize_origins([origin])
