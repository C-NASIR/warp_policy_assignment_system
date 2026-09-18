# PolicyOS MCP server

This service exposes PolicyOS to MCP-compatible agents over Streamable HTTP. It is an authenticated adapter over the FastAPI API: it never connects to PostgreSQL and does not reimplement policy or authorization logic.

## Run locally

Start the backend and frontend first. The frontend is needed for login, MFA, and OAuth consent. Then run from `mcp_server/`:

```bash
cp .env.example .env
uv sync
uv run policyos-mcp
```

Connect the MCP client to <http://127.0.0.1:8001/mcp>. The server advertises OAuth protected-resource metadata; the backend supplies discovery, client registration, authorization code with S256 PKCE, access and refresh tokens, user info, and revocation.

The complete Compose demo starts this service automatically at <http://localhost:8001/mcp>.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `POLICYOS_BACKEND_URL` | `http://127.0.0.1:8000` | Internal FastAPI URL |
| `POLICYOS_OAUTH_ISSUER` | Backend URL | Public OAuth issuer |
| `POLICYOS_MCP_PUBLIC_URL` | `http://127.0.0.1:8001/mcp` | Exact public MCP resource URL |
| `POLICYOS_MCP_HOST` | `127.0.0.1` | Bind host |
| `POLICYOS_MCP_PORT` | `8001` | Bind port |

`POLICYOS_MCP_PUBLIC_URL` must match the backend's `MCP_PUBLIC_URL`. Configure the public issuer, authorization UI, backend OAuth URLs, and MCP resource URL together. Non-loopback production URLs must use HTTPS.

## Authentication and authorization

The agent never receives the user's password or MFA code. Authentication and consent happen in the browser, and every MCP request carries a user-bound OAuth access token. The backend reloads that user's account status, permissions, employee visibility, and assignment-field scope on each request.

Consequently, MCP tools have the same validation, visibility, conflicts, reconciliation, and auditing behavior as the browser application. Human-session operations such as login, password recovery, MFA enrollment, reauthentication, and session management remain browser-only.

## Tool surface

The server currently publishes 52 strictly typed tools:

| Annotation | Count | Examples |
|---|---:|---|
| Read-only | 30 | Search employees, explain assignments, inspect policy impact, query history, review audit and access data |
| Mutating | 18 | Create or update employees, policies, groups, fields, roles, users, and overrides; reconcile an employee |
| Destructive | 4 | Remove an override or role, reset a password, disable a user |

The catalog also provides a non-persisting `preview_change` tool for supported employee, policy, group-membership, and override changes. Agents should identify records with read tools and preview material changes before committing them.

Inputs use strict Pydantic schemas and reject unknown properties before contacting the backend. Paginated backend collections are returned as `{ "items": [...], "page": { "total", "limit", "offset" } }`. Expected backend failures become MCP tool errors containing the HTTP status and the backend's structured category, code, message, issue paths, and metadata; unexpected server errors do not expose internal exception details.

The implementation in `src/policyos_mcp/server.py` is the definitive tool list. Shared input models live in `src/policyos_mcp/schemas.py`.

## Tests

```bash
uv run pytest
```

Tests exercise the Streamable HTTP application, OAuth metadata and token validation, proxy behavior, pagination, strict inputs, tool annotations, and error mapping.
