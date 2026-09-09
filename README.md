# PolicyOS

PolicyOS is a full-stack policy assignment system for turning date-effective workforce rules into explainable employee assignments. Administrators can define policies, target employees directly or through groups, preview their impact, manage approvals and overrides, and inspect both assignment history and audit records.

The repository contains a Next.js web application and a FastAPI API backed by PostgreSQL.

## What the project does

- Builds policies from trusted employee and organization attributes, including derived values such as tenure and reporting relationships.
- Versions policies with effective date ranges and deterministic priority-based conflict resolution.
- Resolves single- and multi-valued assignments while preserving the policy version or override that supplied each value.
- Explains assignment decisions and retains temporal assignment history.
- Supports employee groups, manual overrides, future assignment projections, and scheduled reconciliation.
- Provides preview-and-approval workflows for sensitive changes and an append-only audit trail.
- Enforces role-based permissions, employee visibility scopes, assignment-field scopes, session security, and MFA for privileged users.
- Keeps application-role assignment and revocation as explicit access-administration actions.

## Architecture

```text
Browser
  |
  v
Next.js frontend (localhost:3000)
  |  same-origin proxy and HTTP-only session cookie
  v
FastAPI backend (localhost:8000)
  |
  +--> Policy matching and assignment reconciliation
  +--> Authentication, authorization, approvals, and auditing
  |
  v
PostgreSQL
```

The backend is the source of truth for authentication, authorization, policy evaluation, reconciliation, approvals, and audit data. The frontend performs server-side API calls through a same-origin proxy so browser JavaScript never handles the session token directly.

## Repository layout

```text
.
├── backend/    FastAPI application, domain services, worker, tests, and Alembic scaffold
└── frontend/   Next.js application, UI components, demo data, and API integration
```

See the component guides for deeper technical and operational detail:

- [Backend documentation](backend/README.md)
- [Frontend documentation](frontend/README.md)
- [Learning center plan](docs/learn/README.md)
- [Persistent test seed and fictional company](docs/seed-data-company.md)

## Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL
- Node.js and npm compatible with Next.js 16

## Quick start

### Explore the frontend in demo mode

The UI includes non-persistent demo data and can run without the backend:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Authentication submissions are disabled in demo mode, but the dashboard and primary workflows can be explored.

### Run the complete application

1. Create the local PostgreSQL database:

   ```bash
   createdb policy_assignments
   ```

2. Configure and start the backend:

   ```bash
   cd backend
   cp .env.example .env
   uv sync
   uv run python -m fastapi dev main.py
   ```

   Before using the application beyond local evaluation, replace every `replace-with-a-random-secret` value in `backend/.env`. Generate each secret independently with `openssl rand -hex 32`.

3. In another terminal, configure and start the frontend:

   ```bash
   cd frontend
   cp .env.example .env.local
   npm install
   npm run dev
   ```

4. Open <http://localhost:3000/signup> to create the one-time Root account. After the workspace is initialized, additional users are provisioned by an administrator from **Access control**.

To explore a populated persistent workspace instead, load the test-only Cedar
Harbor Wind Systems tenant before starting the backend:

```bash
./scripts/load_test_data.sh
```

The script creates the disposable `policy_assignments_demo` database when it is
missing and then loads the complete seed atomically.

The backend selects its database through `backend/.env`:

```dotenv
DATABASE_MODE=demo
DATABASE_URL=postgresql+psycopg:///policy_assignments
DEMO_DATABASE_URL=postgresql+psycopg:///policy_assignments_demo
```

Change only `DATABASE_MODE` to `real` or `demo`; the two databases remain
separate.

Read the [company scenario](docs/seed-data-company.md) and use the
[test credentials](docs/seed-data-credentials.txt) to compare roles and workflows.

The API is available at <http://127.0.0.1:8000>, with interactive OpenAPI documentation at <http://127.0.0.1:8000/docs>. The backend creates missing tables at startup; the current Alembic setup does not yet contain migration revisions.

## Scheduled reconciliation

Future policy boundaries and tenure changes are stored as scheduled reconciliation events. Run the one-shot worker from an external scheduler as often as your deployment requires:

```bash
cd backend
uv run python -m app.workers.reconciliation
```

The worker uses a PostgreSQL advisory lock, so overlapping invocations safely leave only one active processor.

## Validation

Backend tests require a dedicated disposable PostgreSQL database because the suite creates and drops application tables:

```bash
createdb policy_assignments_test
cd backend
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/policy_assignments_test \
  uv run pytest
```

Run the frontend checks separately:

```bash
cd frontend
npm run lint
npm run build
```

## Important deployment notes

- PostgreSQL is the only supported database for the API, worker, and tests.
- Set `AUTH_SESSION_COOKIE_SECURE=true` when serving the application over HTTPS.
- Use stable, independently generated secrets and share the same values across all API instances.
- Set `CORS_ALLOWED_ORIGINS` and `NEXT_PUBLIC_SITE_URL` to the exact production frontend origin.
- Run the reconciliation worker through an external scheduler; the API does not start an internal timer.
- Demo mode is intentionally non-persistent and must not be treated as a production data store.
