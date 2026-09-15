# PolicyOS MCP

This component exposes PolicyOS operations to MCP-compatible agents using the
Streamable HTTP transport. It talks to the FastAPI backend over HTTP and never
accesses the PolicyOS database.

## Run locally

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

The initial catalog covers employee search and assignments, batch assignment
queries, policies and impact, groups, field catalogs, audit search, change
previews, employee changes, policy creation and versioning, and assignment
reconciliation. The backend remains authoritative for validation,
authorization, visibility, conflicts, and auditing.
