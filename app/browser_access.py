from __future__ import annotations

import os
from collections.abc import Iterable
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

CORS_ALLOWED_ORIGINS_ENV = "CORS_ALLOWED_ORIGINS"

# Vite uses 5173 by default; 3000 covers common React development servers.
# Deployments should replace this list with their exact frontend origin(s).
DEFAULT_BROWSER_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)

BROWSER_ALLOWED_METHODS = (
    "GET",
    "POST",
    "PATCH",
    "DELETE",
    "OPTIONS",
)
BROWSER_ALLOWED_HEADERS = (
    "Accept",
    "Authorization",
    "Content-Type",
    "X-Actor",
)
BROWSER_EXPOSED_HEADERS = (
    "X-Total-Count",
    "X-Limit",
    "X-Offset",
    "WWW-Authenticate",
)


class BrowserAccessConfigurationError(ValueError):
    """Raised when an allowed browser origin is unsafe or malformed."""


def browser_allowed_origins() -> tuple[str, ...]:
    """Load the exact browser-origin allowlist from the environment.

    An explicitly empty value disables cross-origin browser access. When the
    variable is absent, only common local React development origins are allowed.
    """
    configured = os.getenv(CORS_ALLOWED_ORIGINS_ENV)
    if configured is None:
        return DEFAULT_BROWSER_ORIGINS
    if not configured.strip():
        return ()
    return normalize_origins(configured.split(","))


def normalize_origins(origins: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_origin in origins:
        origin = _normalize_origin(raw_origin)
        if origin in seen:
            continue
        seen.add(origin)
        normalized.append(origin)
    return tuple(normalized)


def configure_browser_access(
    app: FastAPI,
    *,
    allowed_origins: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """Install the browser boundary without weakening API authentication."""
    origins = (
        browser_allowed_origins()
        if allowed_origins is None
        else normalize_origins(allowed_origins)
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=False,
        allow_methods=list(BROWSER_ALLOWED_METHODS),
        allow_headers=list(BROWSER_ALLOWED_HEADERS),
        expose_headers=list(BROWSER_EXPOSED_HEADERS),
        max_age=600,
    )
    app.state.browser_allowed_origins = origins
    return origins


def _normalize_origin(raw_origin: str) -> str:
    origin = raw_origin.strip()
    if not origin:
        raise BrowserAccessConfigurationError(
            f"{CORS_ALLOWED_ORIGINS_ENV} contains an empty origin"
        )
    if origin == "*":
        raise BrowserAccessConfigurationError(
            f"{CORS_ALLOWED_ORIGINS_ENV} must contain exact origins; '*' is not allowed"
        )
    if any(character.isspace() for character in origin):
        raise BrowserAccessConfigurationError(
            f"Invalid origin in {CORS_ALLOWED_ORIGINS_ENV}: {origin!r}"
        )

    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as exc:
        raise BrowserAccessConfigurationError(
            f"Invalid origin in {CORS_ALLOWED_ORIGINS_ENV}: {origin!r}"
        ) from exc

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise BrowserAccessConfigurationError(
            f"Invalid origin in {CORS_ALLOWED_ORIGINS_ENV}: {origin!r}; "
            "use only scheme, host, and optional port"
        )

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    port_suffix = "" if port is None else f":{port}"
    return f"{scheme}://{hostname}{port_suffix}"
