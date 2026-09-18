# PolicyOS frontend

The frontend is the Next.js 16 and React 19 interface for PolicyOS. It covers employee and policy administration, assignment explanations and history, impact previews, groups, overrides, audit records, access control, account security, and the public learning center at `/learn`.

The FastAPI backend remains authoritative for authentication, authorization, validation, reference data, policy evaluation, reconciliation, and audit data. This application owns presentation, navigation, form state, and accessible interaction behavior.

## Run locally

Start the backend first, then run from `frontend/`:

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open <http://localhost:3000>. The Docker image uses Node.js 22; use a current Node.js release compatible with Next.js 16 for local development.

| Variable               | Purpose                                                 |
| ---------------------- | ------------------------------------------------------- |
| `POLICY_API_URL`       | Server-side FastAPI base URL; required                  |
| `NEXT_PUBLIC_SITE_URL` | Public frontend origin used for metadata and OAuth URLs |

The defaults connect to a backend at `http://127.0.0.1:8000`. The complete production-mode demo can instead be started from the repository root with `docker compose up --build`.

## Application behavior

- Server components read backend data directly with the HTTP-only PolicyOS session cookie.
- Browser mutations go through the same-origin `/api/backend/*` proxy. It forwards only the session cookie and approved headers, checks the origin on state-changing requests, and never exposes the session token to client JavaScript.
- Navigation and controls reflect the signed-in user's permissions and record capabilities, but the backend is always the enforcement boundary.
- Directory search, filtering, pagination, form options, previews, and policy resolution come from backend endpoints; there is no offline data or local mutation path.
- `/setup` creates the one-time Root account for an empty workspace. After setup, administrators provision users and roles under `/access`.
- `Command/Ctrl + K` opens Quick Find for pages, actions, and learning content.
- Browsers that implement WebMCP receive five navigation-only tools as progressive enhancement. Operational MCP access is provided by the separate [MCP server](../mcp_server/README.md).

## Learning content

Learning articles live in `content/learn` as schema-validated MDX. `lib/learn-source.ts` defines their metadata contract and ordering; the authoring workflow is documented in [`docs/learn`](../docs/learn/README.md).

Validate learning content after changing articles, metadata, ownership, or links:

```bash
npm run learn:quality
```

## Checks

Run the same frontend checks summarized by the project README:

```bash
npm test
npm run lint
npm run build
```

Use `npm run format:check` to check Prettier formatting and `npm run format` to apply it.

## Code map

```text
app/                    Routes, pages, and route-specific components
app/api/backend/        Same-origin FastAPI proxy
components/features/    Cross-route product features
components/shared/      Reusable domain-aware controls
components/ui/          UI primitives
lib/backend.ts          Server-side API client
lib/permissions.ts      Presentation-level permission helpers
content/learn/          Learning-center MDX
scripts/                Learning-content validation
```
