# PolicyOS MCP

This component exposes PolicyOS operations to MCP-compatible agents using the
Streamable HTTP transport. It talks to the FastAPI backend over HTTP and never
accesses the PolicyOS database.

## Run locally

The default repository Compose stack includes this service at
`http://localhost:8001/mcp` and configures its internal API connection through
the `backend` service. Its container health check uses the MCP server's public,
non-sensitive OAuth protected-resource metadata endpoint at
`/.well-known/oauth-protected-resource/mcp`; no extra application protocol is
introduced.

Start the backend and frontend first, then:

```bash
cp .env.example .env
uv sync
uv run policyos-mcp
```

Connect a client to `http://127.0.0.1:8001/mcp`. The server publishes OAuth
protected-resource metadata, and the PolicyOS backend provides dynamic client
registration, authorization-code plus PKCE, access and refresh tokens, and
revocation. The authorization page is served by the frontend so credentials and
MFA codes never pass through the agent.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `POLICYOS_BACKEND_URL` | `http://127.0.0.1:8000` | Internal backend HTTP URL |
| `POLICYOS_OAUTH_ISSUER` | backend URL | Public OAuth issuer |
| `POLICYOS_MCP_PUBLIC_URL` | `http://127.0.0.1:8001/mcp` | Exact public MCP resource URL |
| `POLICYOS_MCP_HOST` | `127.0.0.1` | Bind host |
| `POLICYOS_MCP_PORT` | `8001` | Bind port |

The public MCP URL must match the backend's `MCP_PUBLIC_URL`. Production issuer,
authorization, redirect, and MCP URLs must use HTTPS.

## Tools

The catalog covers every bearer-authenticated product operation used by the
frontend: employees and assignment history, manual overrides, policies and
impact, groups and their employee/policy attachments, assignment fields,
dashboard and audit data, roles, users, and access reviews. It also provides
batch assignment queries and explicit assignment reconciliation.

Human-session operations remain browser-only: setup, login, logout, password
recovery and self-service changes, MFA enrollment, session management,
reauthentication, and OAuth consent. Those routes require the frontend's secure
session cookie so the connected user's current password and MFA codes never
pass through an agent.

The backend remains authoritative for validation, authorization, visibility,
conflicts, and auditing.

Tool payloads publish strict JSON schemas for the fields accepted by the
backend. Unsupported properties are rejected as MCP argument errors before a
request is sent. Expected backend failures are returned as MCP tool errors with
the HTTP status and the backend's error category, code, message, issue paths,
and metadata (including required permissions when supplied). Unexpected server
failures remain generic so internal exception details are not disclosed.
