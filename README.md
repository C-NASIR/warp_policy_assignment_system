# PolicyOS

An implemented policy-assignment system that turns date-effective workforce rules into deterministic, explainable employee assignments.

This repository is an independent implementation of Warp's **Policy Assignment System** project prompt. It is not an official Warp product.

![PolicyOS explains why a manager received a USD 10,000 expense limit, including the winning policy, matched fact, priority, and candidate decision.](docs/assets/readme/dashboard.png)


## Introduction Video 
[Watch the video here](https://youtu.be/YbF5Kc3qRUs?si=mTDZLY26hp1eVh-q)


## Thirty-second summary

- **Versioned over time:** immutable policy versions have inclusive effective-date ranges; past assignments are recorded, today's are materialized, and future assignments can be calculated without changing state.
- **Deterministic under overlap:** one-valued fields use priority and reject ambiguous equal-priority values; many-valued fields combine unique values with deterministic provenance.
- **Reconciled when inputs change:** employee facts, org relationships, groups, policies, effective dates, and tenure thresholds all drive targeted or scheduled reconciliation.
- **Safe to operate:** employee and policy changes can be previewed through the real domain services before commit.
- **Built to explain:** every assignment stores an immutable explanation; temporal assignment history and the append-only audit journal answer complementary questions.

## Run the complete demo

From the repository root, the complete seeded application starts with one command:

```bash
docker compose up --build
```

The first run builds the images and can take several minutes depending on network and Docker cache. Compose starts PostgreSQL, applies the Alembic migration, loads the fictional Cedar Harbor Wind Systems dataset, and then starts the FastAPI API, production Next.js frontend, demo reconciliation scheduler, and MCP adapter. PostgreSQL remains private to the Compose network.

| Service  | URL                          |
| -------- | ---------------------------- |
| PolicyOS | <http://localhost:3000>      |
| OpenAPI  | <http://localhost:8000/docs> |
| MCP      | <http://localhost:8001/mcp>  |

Useful lifecycle commands:

```bash
docker compose logs -f              # follow the stack
docker compose down                 # stop; preserve demo data
docker compose down -v              # stop and completely reset demo data
./scripts/smoke_test_compose.sh     # verify a running seeded stack
```

The committed Compose secrets and credentials are intentionally public, test-only values for this disposable localhost environment. Do not reuse them.

### Demo login

Start with the seeded Root account, which can inspect every product surface:

```text
Email:    nadia.okafor@cedarharbor.example
Password: HarborRoot!2026
Role:     Root — full workspace visibility
```

The account works immediately for the read and preview walkthrough below. MFA is intentionally unenrolled; privileged writes require the evaluator to enroll a TOTP authenticator first. See [all fictional accounts](docs/seed-data-credentials.txt) to compare scoped roles. None of these credentials is suitable for a real environment.

## Five-minute walkthrough

1. Sign in at <http://localhost:3000/login> and open **Employees**.
2. Open **Rafael Morales** (`/employees/6`). Expand **Expense Approval Limit** to see the winning priority-45 policy, its `Is Manager` evidence, and the lower-priority candidates. Expand **Inspection Evidence Vault** to see a group-derived policy origin.
3. Open **Priya Raman** (`/employees/10`). Expand **Expense Approval Limit** to see a manual value and the policy result it replaced.
4. Still on Priya, choose **Edit employee**, change Department from Engineering to Product, and select **Review assignments**. The engine previews three changed assignment fields without persisting the proposal; close the editor rather than confirming it.
5. Open **People Manager Responsibilities** (`/policies/8`) to inspect its rule, outputs, dated version history, and population impact.
6. Return to either employee for recorded **Past assignments**, then open **Audit log** for actor, mutation, and assignment events.
7. Optional: sign in as Priya, Elena, Rafael, or Kai using the [role comparison credentials](docs/seed-data-credentials.txt) to see action, employee, and assignment-field scopes applied together.
8. Optional: connect an MCP-compatible client to `http://localhost:8001/mcp`, authorize as a seeded user, and ask it to explain Priya Raman's expense limit or preview her move from Engineering to Product.

## Scoped human access

PolicyOS supports multiple application users through role-based access control with independent data-visibility scopes. This is more precise than a simple administrator/member hierarchy:

- User accounts are created explicitly and remain separate from employee records. Recording a manager or employee never grants application access by itself.
- Reusable roles bundle action permissions with an employee scope (`all`, `reporting_tree`, `self`, or `none`) and an assignment-field scope (`all`, `selected`, or `none`).
- A user can hold multiple roles. Their allowed actions and visible data are the union of those grants; a narrow role does not override a broader grant.
- Reporting-tree access follows the linked employee's direct and indirect reports, while selected-field scope can expose only the assignment domains relevant to that operator.
- The backend applies these boundaries to records, derived assignments, previews, audit data, browser sessions, and user-bound MCP agents. Out-of-scope direct resources are hidden with `404` responses.
- Access review surfaces privileged users without MFA, stale users, unused roles, and roles with broad scopes.

This is scoped authorization inside one workspace, not SaaS multitenancy. The current data model has no tenant partition; supporting isolated customer organizations would require an explicit tenant boundary throughout storage, queries, credentials, and audit data. See [Manage access](frontend/content/learn/policyos/manage-access.mdx), [Limit access with scopes](frontend/content/learn/policyos/limit-access-with-scopes.mdx), and the [backend authorization model](backend/README.md#authentication-and-authorization).

## AI-native administration through MCP

PolicyOS also exposes an optional Model Context Protocol server, allowing MCP-compatible agents to inspect and administer the policy system using natural language.

The MCP adapter publishes 52 strictly typed tools covering employee search, assignment explanations and history, policy impact, change previews, groups, manual overrides, reconciliation, audit records, roles, users, and access reviews.

Example agent requests include:

- “Explain why Priya has a USD 5,000 expense approval limit and show what the policy engine would assign without her override.”
- “Preview the assignment changes if Priya moves from Engineering to Product. Do not save anything.”
- “Find California employees and show which policies apply to them today.”
- “Show the population affected by the People Manager Responsibilities policy.”
- “Reconcile Rafael’s assignments and explain any resulting changes.”

This is intentionally an interface over the existing application—not a second implementation of its business logic:

- The MCP server communicates only with FastAPI and never accesses PostgreSQL directly.
- Agents authenticate through OAuth authorization code flow with PKCE.
- Authorization is user-bound, so agents inherit the connected administrator’s permissions and employee visibility.
- The frontend handles login, MFA, and consent; credentials never pass through the agent.
- Tools publish strict input schemas and distinguish read-only, mutating, and destructive operations.
- Material changes can be previewed through the real rollback-only domain workflow before being committed.
- Agent activity passes through the same validation, reconciliation, and audit paths as browser activity.

This keeps the assignment engine deterministic and auditable while making the system ready for AI-native operational workflows.

See the [MCP adapter documentation](mcp_server/README.md) for connection, authentication, tool coverage, and local setup.

## Warp criteria mapped to implementation

| Warp criterion                       | PolicyOS implementation                                                                                                                                                                                                                                                                         |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Define assignment rules              | Administrators build nested rules from trusted employee, department, location, tenure, and org-chart fields, then attach policies to explicit groups when needed. Canonical trees are compiled to OR-of-AND clauses. [Compiler tests](backend/tests/test_policy_compiler.py)                    |
| Resolve an employee set for any date | Batch queries distinguish recorded history for past dates, persisted assignments for today, and non-persisting calculation for future dates. [Assignment-query tests](backend/tests/test_assignment_queries.py)                                                                                 |
| Cardinality and conflicts            | Fields declare `one` or `many`. Highest priority resolves `one`; equal-priority different values return a structured conflict. `many` unions values and selects duplicate provenance deterministically. [Resolution tests](backend/tests/test_assignment_values.py)                             |
| Reconcile changing inputs            | Employee and manager changes, group membership and attachments, policy mutations, policy boundaries, and tenure anniversaries flow through the same resolver. Due events are processed by an advisory-locked worker. [Reconciliation tests](backend/tests/test_policy_change_reconciliation.py) |
| Non-engineer UX                      | Guided policy authoring, employee onboarding, previews, lifecycle controls, explanations, history, groups, overrides, audit filters, and an in-product learning center are implemented in the Next.js application. [Frontend guide](frontend/README.md)                                         |
| Explainability and auditability      | Materialized assignments retain policy/override provenance, match evidence, candidate outcomes, and decision strategy. Assignment history records what was true; the transactional audit journal records who changed what. [Explanation tests](backend/tests/test_assignment_explanations.py)   |
| Architecture and scale judgment      | PostgreSQL transactions and constraints protect the current synchronous model; the full-population policy fan-out is identified explicitly, with an outbox/batched evolution path. [System design](docs/system-design.md#12-scaling-characteristics)                                            |
| Developer experience                 | One-command Compose startup, Alembic-owned schema, health-gated services, an idempotent seed, OpenAPI, smoke tests, and focused component/domain suites make the system runnable and inspectable. [Compose file](compose.yaml)                                                                  |
| AI-native extension                  | A 52-tool Streamable HTTP MCP server exposes the product through user-bound OAuth/PKCE while preserving backend authorization, previews, validation, and audit behavior. [MCP adapter](mcp_server/README.md)                                                                                    |

## Core resolution model

```mermaid
flowchart LR
    F["Employee facts<br/>and org context"] --> V["Effective<br/>policy versions"]
    V --> M["Direct and<br/>group matches"]
    M --> C["Candidate<br/>field values"]
    C --> R["Cardinality and<br/>priority resolution"]
    R --> O["Manual<br/>overrides"]
    O --> A["Temporal assignments<br/>with explanations"]
```

For a one-valued field, the highest priority wins only when the candidates at that priority agree; conflicting values are rejected rather than silently tie-broken. A many-valued field combines unique values, choosing a duplicate value's recorded source by priority and then policy-version ID. Active overrides replace every policy-derived value for their field, but do not conceal a policy conflict. Every persisted result stores the exact explanation used at resolution time.

## Architecture

```mermaid
flowchart LR
    B[Browser] -->|HTTP-only session| N["Next.js UI<br/>same-origin proxy"]
    N --> A["FastAPI<br/>authorization boundary"]
    M["Optional MCP adapter<br/>OAuth user token"] --> A
    S["Demo scheduler"] --> W["One-shot<br/>reconciliation worker"]
    A --> E["Policy engine and<br/>domain services"]
    W --> E
    E --> P[(PostgreSQL)]
```

FastAPI and the shared domain services own validation, authorization, resolution, reconciliation, and audit writes. PostgreSQL is the source of truth; Alembic alone changes its schema. Browser requests pass through a same-origin Next.js proxy so JavaScript never handles the session token. The worker uses the same services as API mutations; Compose invokes its one-shot command on a demo-only interval. MCP is an optional HTTP adapter over the same user authorization model, not a separate data path.

Read the [system design](docs/system-design.md) for the domain model, time semantics, invariants, failure handling, and scaling path.

## Product evidence

### Preview before mutation

![PolicyOS previews the assignment changes caused by moving Priya Raman from Engineering to Product before the change is confirmed.](docs/assets/readme/change-preview.png)

The preview runs the real employee mutation and reconciliation services inside a savepoint that is always rolled back.

### Versioned policy and population impact

![People Manager Responsibilities shows its rule, three assignment outputs, version number, effective date, priority, and population impact.](docs/assets/readme/policy-impact-and-version.png)

### Override provenance

![Priya Raman's manual USD 5,000 expense limit shows the USD 2,500 policy result it replaced and the stored decision strategy.](docs/assets/readme/manual-override-provenance.png)

## Correctness highlights

- A policy has at most one effective version on a date; overlapping version ranges are rejected.
- Equal-priority, different values for a one-valued field are explicit conflicts.
- Each assignment has exactly one source: a policy version or an override.
- Assignment history uses validated half-open `[effective_from, effective_until)` intervals.
- Reconciliation locks open rows and rejects writes earlier than established history.
- Manager updates reject missing managers, self-management, and reporting cycles.
- Preview and commit call the same domain services; previews are rollback-only.
- Domain mutations, assignment changes, schedules, and audit entries share transactions.
- Scheduled events have unique identities; the worker uses an advisory lock and locked batches for safe retries.

The enforcement split between database constraints and service invariants is documented in [Correctness invariants](docs/system-design.md#8-correctness-invariants).

## Testing and verification

Current verified results:

- **Backend:** 224 tests passed.
- **Frontend:** 20 Vitest component/unit tests passed; ESLint and the Next.js production build passed.
- **MCP adapter:** 7 tests passed.
- **Database:** `alembic check` reported no model/migration drift.
- **Docker:** clean production image build and seeded startup passed; the smoke test verified service health, public URLs, authenticated seed data, migration head, and seed/migration idempotence.

The normal validation entry points are:

```bash
# Backend (requires a dedicated disposable PostgreSQL database)
cd backend
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/policy_assignments_test uv run pytest

# Frontend
cd ../frontend
npm test && npm run lint && npm run build

# MCP adapter
cd ../mcp_server
uv run pytest

# With the Compose demo running
cd ..
docker compose exec -T backend alembic check
./scripts/smoke_test_compose.sh
```

Tests cover resolution, version boundaries, group and org-chart rules, tenure scheduling, reconciliation, history, previews, explanations, authorization, visibility, audit behavior, migrations, and the demo seed. The repository currently has a focused learning-content workflow rather than a badge-worthy comprehensive CI pipeline, so no CI status is implied here.

## Technology choices

| Choice                 | Why it is here                                                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Next.js 16 + React 19  | Product UI, server-rendered routes, and the same-origin session proxy.                                                          |
| FastAPI + Pydantic     | Typed HTTP contracts around explicit domain services and structured conflicts.                                                  |
| SQLAlchemy 2 + Alembic | Transactional mappings with a single, reviewable schema lifecycle.                                                              |
| PostgreSQL 17          | Referential integrity, temporal indexes, JSON explanation snapshots, row locks, advisory locks, and transactional audit writes. |
| MCP + OAuth/PKCE       | Optional user-bound agent access without bypassing backend authorization.                                                       |
| Docker Compose         | A reproducible evaluator environment with health-gated startup and seeded data.                                                 |

## Tradeoffs and current boundaries

PolicyOS deliberately favors immediate, inspectable correctness over maximum write throughput. Material policy changes and their previews currently consider the full employee population synchronously; batch resolution deduplicates IDs but still evaluates employees individually. The natural scale evolution is an atomic outbox plus dependency-indexed, idempotent reconciliation batches—not an implemented queue hidden behind a claim.

Future calculations apply future policy versions and date-derived tenure to **current** employee facts, org relationships, groups, and overrides. Historical employee facts are not independently versioned, so assignment history is authoritative but retroactive recomputation is not offered. The current model is one workspace, not explicit SaaS multi-tenancy. Scheduled future employee facts, time-bounded overrides, production scheduling, and queue/observability infrastructure remain outside this version.

See [Scaling characteristics](docs/system-design.md#12-scaling-characteristics) and [Current boundaries](docs/system-design.md#14-current-boundaries) for the complete distinction between implemented behavior and evolution paths.

## Repository guide

```text
backend/      FastAPI application, policy engine, worker, migrations, tests
frontend/     Next.js product UI, explanation components, learning center
mcp_server/   Optional Streamable HTTP MCP adapter
docs/         System design, demo scenario, credentials, learning materials
scripts/      Demo seed and Compose smoke-test entry points
compose.yaml  Complete evaluator stack
```

- [System design](docs/system-design.md)
- [Backend behavior and API](backend/README.md)
- [Frontend guide](frontend/README.md)
- [MCP adapter](mcp_server/README.md)
- [Cedar Harbor demo company](docs/seed-data-company.md)
- [Test-only credentials](docs/seed-data-credentials.txt)

### Local development without Docker

Manual development remains available but is intentionally secondary to the evaluator demo. Use the [backend setup](backend/README.md#install-and-run), [frontend setup](frontend/README.md#run-locally), and [MCP setup](mcp_server/README.md#run-locally). PostgreSQL is required, and `uv run alembic upgrade head` must run before the API or worker; application startup verifies the migration head and never creates schema.

---

The design preference throughout is correctness before optimization: explicit conflicts instead of silent ambiguity, preview before mutation, and stored provenance instead of explanations reconstructed after the facts have changed.
