# PolicyOS backend

The backend is the authoritative FastAPI service for PolicyOS. It owns validation, authentication and authorization, policy evaluation, assignment reconciliation, temporal history, previews, and audit writes. PostgreSQL is the only supported database, and Alembic is the only schema-management path.

For product behavior and cross-component architecture, see the [project README](../README.md) and [system design](../docs/system-design.md). The exact HTTP contract is generated from the running application at <http://127.0.0.1:8000/docs>.

## Core behavior

- Policies have immutable, inclusive date-effective versions. Conditions are compiled to OR-of-AND clauses over trusted employee and organization fields.
- Assignment fields are either `one` or `many`. A one-valued field rejects different values tied at the winning priority; a many-valued field unions unique values with deterministic provenance.
- Groups contribute policies to their members. Manual overrides replace policy-derived values for one field, but do not hide policy conflicts.
- Every persisted assignment has a half-open `[effective_from, effective_until)` interval and an immutable explanation snapshot.
- Past assignment queries use recorded history, today uses materialized state, and future queries calculate without persisting.
- Employee, manager, group, policy, and override changes reconcile affected assignments in the same transaction. Change previews run those same services inside a savepoint that is always rolled back.
- Audit entries commit with the mutation they describe. Scheduled policy boundaries and tenure anniversaries are handled by the reconciliation worker.

## Install and run

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), and PostgreSQL.

From `backend/`:

```bash
createdb policy_assignments
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run python -m fastapi dev main.py
```

Replace every `replace-with-a-random-secret` value in `.env` before creating accounts or credentials. Generate each value independently with `openssl rand -hex 32`.

The API starts at <http://127.0.0.1:8000>. Swagger UI is at <http://127.0.0.1:8000/docs>, and the OpenAPI schema is at <http://127.0.0.1:8000/openapi.json>. Startup fails if the selected database is not at the current migration head. It maintains trusted condition-field catalog rows but never creates or upgrades schema.

The repository-wide seeded environment remains the quickest way to run the complete product:

```bash
cd ..
docker compose up --build
```

## Configuration

Use `.env.example` as the source of truth for local settings. The important groups are:

| Setting | Purpose |
|---|---|
| `DATABASE_MODE` | Selects `DATABASE_URL` (`real`) or `DEMO_DATABASE_URL` (`demo`) |
| `AUTH_*` | Session, MFA, recovery, bootstrap-credential, and local password-reset behavior |
| `CORS_ALLOWED_ORIGINS` | Exact browser origins allowed to call the API |
| `OAUTH_*`, `MCP_PUBLIC_URL` | User-bound OAuth endpoints and MCP resource identity |

The defaults are for local HTTP development. Production session, OAuth, authorization, redirect, and MCP URLs must be configured together for HTTPS, and all secret values must come from a secret manager.

## Database and migrations

Apply migrations before the API, seed loader, or worker starts:

```bash
uv run alembic upgrade head
```

After changing SQLAlchemy models:

```bash
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
uv run alembic check
```

Always review generated revisions. Do not use `alembic stamp` on an empty, older, or manually altered database.

To load the fictional Cedar Harbor dataset into a separate local demo database, run from the repository root:

```bash
./scripts/load_test_data.sh
```

The loader migrates the database, refuses unrelated existing data, and is idempotent for its own completed seed. See the [company guide](../docs/seed-data-company.md) and [test-only credentials](../docs/seed-data-credentials.txt).

## Authentication and authorization

The API supports three credential paths:

- Browser users authenticate with an HTTP-only session cookie. Privileged users must enroll TOTP MFA by default.
- Interactive MCP clients use OAuth authorization code with S256 PKCE; each access token resolves to the current PolicyOS user and current role scopes.
- Unattended automation can use revocable bearer API credentials with coarse operation scopes.

Non-Root users receive the union of their roles. Roles combine action permissions with independent employee visibility and assignment-field scopes. The backend enforces both scopes on records, derived results, previews, and audit data; direct requests for out-of-scope resources return `404`.

All protected operations publish `x-required-permissions` and `x-required-scopes` in OpenAPI. Structured error responses include a stable category, code, message, issue paths, and relevant metadata.

## Collections and time-based queries

Collection endpoints use `limit` and `offset` and return pagination metadata in `X-Total-Count`, `X-Limit`, and `X-Offset`. Supported filters and response models are documented in OpenAPI rather than duplicated here.

`POST /assignment-queries` has three explicit modes based on `evaluation_date`:

| Date | Mode | Source |
|---|---|---|
| Past | `recorded_history` | Persisted assignment history at the start of that UTC date |
| Today | `current_persisted` | Current materialized assignments |
| Future | `calculated_future` | Current employee facts plus policies and date-derived facts evaluated for that date, without persistence |

Future calculation does not predict future employee facts, reporting relationships, group membership, policy status, or overrides. Historical employee facts are not independently versioned.

## Reconciliation worker

Run the one-shot worker under an external scheduler:

```bash
DATABASE_MODE=real DATABASE_URL=postgresql+psycopg://user:password@host/database \
uv run python -m app.workers.reconciliation
```

It uses a PostgreSQL advisory lock, processes due events in locked batches, and exits successfully when another worker owns the lock. Configuration:

| Variable | Default |
|---|---:|
| `RECONCILIATION_BATCH_SIZE` | `50` |
| `RECONCILIATION_MAX_RUNTIME_SECONDS` | `900` |
| `RECONCILIATION_ADVISORY_LOCK_KEY` | `8675309001` |
| `LOG_LEVEL` | `INFO` |

Compose wraps this one-shot command in a demo-only polling loop. Production needs a real scheduler.

## Tests

Tests create and drop application tables. Always use a dedicated disposable database:

```bash
createdb policy_assignments_test
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000 \
TEST_DATABASE_URL=postgresql+psycopg:///policy_assignments_test \
uv run pytest
```

Useful focused runs include `uv run pytest tests/test_assignment_values.py` for resolution, `tests/test_policy_change_reconciliation.py` for propagation, and `tests/test_access_control.py` for authorization.

## Operations

If both the Root password and MFA recovery methods are lost, run the interactive recovery tool on a trusted host with database access:

```bash
AUTH_ROOT_RECOVERY_KEY='value-from-your-secret-manager' \
uv run python scripts/emergency_root_recovery.py root@example.com
```

It resets the password, disables MFA, revokes Root sessions, and records security and audit events. Re-enroll MFA and rotate the recovery key immediately afterward.

## Code map

```text
app/routers/    HTTP endpoints
app/services/   Domain behavior and authorization
app/models.py   SQLAlchemy mappings
app/schemas.py  API request and response models
app/workers/    One-shot scheduled reconciliation worker
alembic/        Schema migration history
scripts/        Seed and emergency-recovery commands
tests/          API, domain, security, migration, and seed tests
```
