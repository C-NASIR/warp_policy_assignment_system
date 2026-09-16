# Warp Policy Assignment System

Version 1 is a FastAPI backend that records past assignments, serves current assignments, and calculates future assignments from date-effective policies.

## Architecture

The application uses FastAPI and Pydantic at the API boundary, explicit application services for domain behavior, SQLAlchemy 2 for persistence, and PostgreSQL through Psycopg 3. PostgreSQL is the only supported database for the API, worker, and tests. The schema is created directly from the application models.

```text
Employee
→ Direct Compiled Policy Matching + Group Policies
→ Stable Employee Policies
→ Effective Policy Versions
→ Candidate Field Values
→ Conflict Resolution
→ Employee Overrides
→ Temporal Employee Assignments
```

Read-only assignment queries distinguish three questions. A past date reads the
persisted `EmployeeAssignment` history at the start of that UTC date, today reads
the current persisted rows, and a future date runs stateless policy resolution
without changing policy links, assignments, schedules, or audit logs. Exact
historical instants remain available through the existing `as_of` timestamp.
Reconciliation uses the same stateless resolver for today and then persists its
calculated policy links and assignment differences.

`Policy` is the stable identity referenced by employees and groups. `PolicyVersion` is the executable definition containing priority, effective dates, conditions, compiled clauses, and field values. Policy condition trees are compiled into flat OR-of-AND clauses per version. Employee reconciliation selects the one version effective on the evaluation date, evaluates its clauses, persists stable policy links, and resolves each assignment field independently.

Policy-version API responses include the complete canonical condition tree using
the same nested `logical_operator`, `conditions`, and `child_groups` structure
accepted when creating a version. This lets clients inspect and round-trip a
stored rule without depending on its internal compiled representation.

Condition inputs are system-controlled `ConditionFieldDefinition` records, separate from assignment-output `AssignmentFieldDefinition` records. Static fields resolve trusted employee attributes; derived fields invoke allowlisted application resolvers. Definitions declare descriptions, data types, allowed operators, rule-builder input metadata, resolver keys, and dependency metadata, while canonical and compiled conditions retain foreign keys to those definitions. The condition-field API exposes that catalog so visual and agent clients can construct valid conditions without duplicating field-specific rules. Administrators select catalog fields but cannot define arbitrary formulas or executable resolvers.

`tenure` is a derived calendar-duration field resolved from `Employee.start_date` and the reconciliation evaluation date. Inputs such as `2 years` are normalized to `P2Y`; comparison uses completed calendar anniversaries rather than fixed 365-day intervals. A February 29 start date reaches its anniversary on February 28 in a non-leap year.

The employee reporting graph is a self-referencing `manager_id` relationship with database-enforced referential integrity. Policies can use the static `manager_id` reference or the derived `is_manager`, `direct_report_count`, `reports_under`, and `management_level` fields. `reports_under = N` matches any direct or indirect report beneath employee `N`; management level is the number of reporting hops from a root employee, so a root has level zero. Manager changes reject missing managers, self-management, and cycles. Dependency impact resolvers synchronously reconcile the moved employee and descendants plus the old and new managers in the same transaction.

Effective ranges are inclusive. Versions for one policy may not overlap, and an archived policy has no effective version. Scheduling a later version automatically closes the previous open-ended version on the preceding day. An effective-date gap is valid and means that policy contributes no behavior during the gap. Creating a future version immediately reconciles current state but does not apply that version early; automatic reconciliation when its effective date arrives remains a separate scheduling concern.

Future changes are represented centrally in `ScheduledReconciliation` while their authoritative dates remain on the owning domain records. Policy-version creation immediately synchronizes pending `becomes_effective` and `expires` events. Because `effective_until` is inclusive, expiration is scheduled for midnight UTC on the following day. The scheduling service can query and reconcile due events transactionally, but version 1 does not include a periodic worker that invokes it.

Groups are explicit collections of employees. A group contributes its attached policies as candidates for every member; it does not produce assignments of its own. Direct matches and group-inherited policies are deduplicated and sent through the same policy engine, so priority and conflict behavior is identical regardless of where a policy came from.

For cardinality `one`, the highest-priority effective policy version wins. Equal-priority versions producing different values return HTTP 409 instead of selecting arbitrarily. For cardinality `many`, unique values are retained. If several versions produce the same many-valued result, its recorded source is the highest-priority version, breaking remaining ties by lowest version ID.

Manual overrides are field values applied after normal policy resolution. If a field has overrides, all policy-derived values for that field are replaced by its override values. A `one` field accepts one override per employee; a `many` field accepts multiple unique override values. Overrides can also create an assignment when no policy supplies that field. They do not suppress policy conflicts, which remain configuration errors.

Employee assignments are temporal results, not independently versioned definitions. Each row has a UTC `effective_from` and optional `effective_until`, using a half-open `[effective_from, effective_until)` interval. Reconciliation compares the newly resolved result with open assignments: unchanged values and sources retain their rows, removed results are closed, and new or changed results create new rows. This preserves both what an employee had at an instant and the exact policy version or override that supplied it.

Every assignment also stores an immutable JSON explanation snapshot built during
resolution. Policy explanations record the winning policy and version, direct
condition evidence or group origins, the field's cardinality and selection
strategy, and competing candidates with their priorities and outcomes. Override
explanations identify the override and the policy values it replaced. A material
explanation change closes the old assignment and creates a new historical row
even when the final value and winning source remain unchanged. Assignment-query
reads return that complete stored explanation. Employee detail reads project a
typed display summary, and history lists omit explanation payloads entirely.
Future projections build the complete shape in memory without persisting it.

`AuditLog` is the system-wide mutation journal. Assignment history answers what was true at a point in time; audit logs answer what changed, when, and which actor caused it. Audit entries are written through one service in the same database transaction as the domain mutation, so both the mutation and its audit entries commit or roll back together. API mutations use the authenticated credential's subject as their actor. `X-Actor` is accepted only from a credential with `actor:override`; this makes delegated attribution explicit instead of allowing callers to spoof it. Automated reconciliation always records assignment mutations as `system`.

Overrides are retained for provenance. Updating an override retires the old immutable row and creates a replacement; deleting one retires it. Only unretired overrides participate in current resolution, while historical assignments can continue referring to the override that produced them.

## Domain concepts

- **Employee:** current name, U.S. state or territory, department, employee type, location, start date, and an optional self-referencing manager relationship. The physical `state_code` column stores the canonical two-letter code.
- **Group:** a named collection of employees that can supply policies to its members.
- **Employee group membership:** the many-to-many link between employees and groups.
- **Group policy:** the many-to-many link that makes a policy apply to every member of a group.
- **Policy:** a stable named identity with `draft`, `active`, or `archived` status. Draft policies can be authored without affecting assignments and require separate activation authority before they participate in resolution.
- **Policy version:** a date-effective, priority-ranked executable definition owned by one policy.
- **Condition field definition:** a system-controlled static or derived policy input with a trusted resolver, data type, and dependency metadata.
- **Condition tree:** a version-owned nested `and`/`or` expression over condition fields using `=`, `<`, `<=`, `>`, and `>=` comparisons.
- **Compiled policy clause:** one version-owned flat set of conditions that must all match.
- **Employee policy:** a persisted match between an employee and a policy.
- **Assignment field definition:** a named assignment output with `one` or `many` cardinality and either a controlled option list or an explicitly chosen free-text input.
- **Policy field value:** one relationally stored consequence of a policy version.
- **Employee override:** one employee-specific field value that replaces policy results for that field; retired rows remain available as historical sources.
- **Employee assignment:** a time-bounded resolved value supplied by exactly one policy version or employee override, with an immutable explanation of the decision.
- **Audit log:** an append-only actor, entity, action, before/after snapshot, and timestamp for an important domain mutation.
- **User:** a human account with a normalized email, Argon2id password hash, lifecycle status, one or more assigned roles, and an optional employee link. Administratively reset passwords are temporary and must be changed at the next login.
- **Role:** a reusable, named bundle of application permissions plus an employee-data scope, assigned many-to-many to non-Root users.
- **Role permission:** one allow-only capability such as `employees:read`, `policies:update`, `policies:version:create`, `policies:activate`, or `access:manage`. Effective permissions are the union of every assigned role.
- **Employee-data scope:** a role-level visibility boundary of `all`, `reporting_tree`, `self`, or `none`. A user's effective employee visibility is the union of every assigned role; reporting-tree access starts from the employee linked to that user and includes every direct and indirect report.
- **Assignment-field scope:** a separate role-level data boundary of `all`, `selected`, or `none`. Selected roles name the assignment domains they can access, such as Application Access or Pay Schedule. Effective access is the union across roles, while any `all` role grants every assignment field.
- **Authentication session:** a revocable, expiring human login session whose opaque browser token is stored only as a SHA-256 hash.
- **API credential:** a revocable, optionally expiring bearer credential whose opaque token is stored only as a SHA-256 hash and grants named operation scopes.
- **Scheduled reconciliation:** a centralized pending, processed, or cancelled future trigger referencing the domain entity whose date caused it.

## Install and run

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are expected.

```bash
uv sync
export DATABASE_MODE=real
export DATABASE_URL=postgresql+psycopg:///policy_assignments
export AUTH_BOOTSTRAP_TOKEN="$(openssl rand -hex 32)"
export AUTH_BOOTSTRAP_SUBJECT=local-admin
export AUTH_SESSION_COOKIE_SECURE=false
export AUTH_MFA_ENCRYPTION_KEY="$(openssl rand -hex 32)"
export AUTH_ROOT_RECOVERY_KEY="$(openssl rand -hex 32)"
export CORS_ALLOWED_ORIGINS=http://localhost:3000
uv run python -m fastapi dev main.py
```

The API runs at <http://127.0.0.1:8000>; interactive documentation is at <http://127.0.0.1:8000/docs>. A PostgreSQL server and database must exist before startup. The URL above is also the local default when `DATABASE_URL` is omitted; set it explicitly outside local development. Plain `postgresql://` URLs are accepted and normalized to the installed Psycopg 3 driver. Any non-PostgreSQL URL is rejected at startup. Missing tables are created directly from the application models on startup.

Every business API endpoint except `GET /` requires either a valid human session or `Authorization: Bearer <credential>`. The frontend creates the one-time Root account through `POST /auth/setup-root`, then uses login sessions stored in an HTTP-only, SameSite `strict` cookie. Root is an immutable break-glass superuser; other users receive the union of their assigned role permissions, employee-data scopes, and assignment-field scopes. Employee scope is enforced on employee records and every employee-derived result. Assignment-field scope independently filters assignment fields, policies, assignments, overrides, summaries, group-policy links, change previews, and related audit events. A policy is accessible only when every output in every version belongs to the user's visible assignment fields, preventing partial edits to mixed-domain policies. Out-of-scope direct resource requests return 404 so they do not disclose whether the record exists. Policy responses include record-specific `can_update`, `can_create_version`, `can_activate`, and `can_archive` capabilities. These combine the caller's granular action permissions, assignment-field scope, and the record lifecycle state; the frontend consumes them while the API remains the final enforcement boundary. Permission and scope changes take effect on the next request, including for existing sessions.

`AUTH_SESSION_TTL_SECONDS` defaults to 12 hours, idle sessions expire after 30 minutes (`AUTH_SESSION_IDLE_TTL_SECONDS`), and sensitive administrative changes require authentication within the last 10 minutes (`AUTH_REAUTH_TTL_SECONDS`). `AUTH_SESSION_COOKIE_SECURE` must be `true` behind production HTTPS. Passwords use Argon2id; only session-token hashes are stored in PostgreSQL. State-changing session requests also require a trusted `Origin`. Root and privileged sessions must enroll TOTP MFA by default. `AUTH_MFA_ENCRYPTION_KEY` must be a stable secret of at least 32 bytes shared by every API process. Recovery codes are stored as one-time Argon2id hashes. Password-reset responses never expose their token unless `AUTH_PASSWORD_RESET_EXPOSE_TOKEN=true` is intentionally enabled for a local delivery adapter or test environment.

### Emergency Root recovery

Use this only when both the Root password and MFA recovery methods are lost. Run it interactively on a trusted application host with database access; never put the recovery key or new password in shell history.

```bash
cd backend
export DATABASE_MODE=real
export DATABASE_URL=postgresql+psycopg:///policy_assignments
export AUTH_ROOT_RECOVERY_KEY='value-from-your-secret-manager'
uv run python scripts/emergency_root_recovery.py root@example.com
```

The tool verifies the separately stored recovery key, prompts for a new password, disables MFA, revokes every Root session, and writes both a critical security event and audit entry in the same transaction. After recovery, sign in, enroll MFA immediately, store the new recovery codes offline, review the access report and security events, then rotate `AUTH_ROOT_RECOVERY_KEY`.

Bearer API credentials remain the machine-to-machine authentication mechanism for unattended automation. The MCP server uses a separate OAuth authorization-code flow with PKCE so interactive agent requests retain the connected user's PolicyOS identity. The bootstrap token grants all operations and exists only to issue the first persistent API credential. It must contain at least 32 bytes, must be stored in the deployment secret manager, and should be removed after administrative credentials have been issued. `AUTH_BOOTSTRAP_SUBJECT` controls its audit identity and defaults to `bootstrap`. Newly issued `wpa_...`, `poa_...`, and `por_...` secrets are stored only as SHA-256 hashes. Browser code must never contain a shared API credential.

Run tests with:

```bash
createdb -U postgres policy_assignments_test
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/policy_assignments_test \
uv run pytest
```

### Persistent test seed

To evaluate the complete application with realistic, related records, run the
repository helper from the project root:

```bash
./scripts/load_test_data.sh
```

The helper creates `policy_assignments_demo` when needed. The seed operation is
atomic, refuses databases containing tenant data, and is safe to repeat after
this exact seed has completed. It includes employee and reporting
relationships, users and scoped roles, dated policies and assignments, groups,
overrides, schedules, security history, API credentials, and audit
logs. See [the company guide](../docs/seed-data-company.md) and
[plaintext test credentials](../docs/seed-data-credentials.txt). MFA is left
unenrolled intentionally so each tester can configure it manually.

Select which database the backend uses in `.env`:

```dotenv
DATABASE_MODE=demo
DATABASE_URL=postgresql+psycopg:///policy_assignments
DEMO_DATABASE_URL=postgresql+psycopg:///policy_assignments_demo
```

`real` selects `DATABASE_URL`; `demo` selects `DEMO_DATABASE_URL`. Invalid mode
names fail at startup instead of silently connecting to the wrong database.

Tests create and drop all application tables, so `TEST_DATABASE_URL` must point to a dedicated disposable PostgreSQL database. It defaults to the local `policy_assignments_test` database shown above.

## Browser access

The API accepts cross-origin requests only from exact origins in the
comma-separated `CORS_ALLOWED_ORIGINS` environment variable. When it is not
set, local React development servers at `localhost` and `127.0.0.1` on ports
`5173` and `3000` are allowed. Set the deployment's exact HTTPS frontend
origin explicitly in production. Set the variable to an empty string to
disable cross-origin browser access; wildcard origins and values containing a
path, query, fragment, or user information are rejected at startup.

Browser preflight supports the API's `GET`, `POST`, `PATCH`, `DELETE`, and
`OPTIONS` methods plus `Authorization`, `Content-Type`, `Accept`, and the
scope-controlled `X-Actor` request header. JavaScript can read
`X-Total-Count`, `X-Limit`, `X-Offset`, and `WWW-Authenticate` response headers.
Preflight itself is unauthenticated, while every protected API operation still
requires its bearer credential and operation scope.

Cross-origin cookie credentials remain disabled. The Next.js frontend receives
the HTTP-only session cookie on its own origin and forwards it to FastAPI through
its same-origin server proxy. CORS is only a browser boundary and does not grant
API access. Both the frontend proxy and backend validate the origin of
state-changing cookie-authenticated requests.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Health check |
| GET | `/auth/setup-status` | Report whether the one-time Root setup is available |
| POST | `/auth/setup-root` | Create the first Root user and start a session |
| POST | `/auth/login` | Authenticate a human user and start a session |
| GET | `/auth/me` | Read the signed-in human user |
| POST | `/auth/logout` | Revoke the current human session |
| POST | `/auth/change-password` | Change the password, revoke other sessions, and rotate the current session |
| POST | `/auth/password-reset/request` | Generate a short-lived, single-use account recovery token without disclosing account existence |
| POST | `/auth/password-reset/confirm` | Reset a password and revoke every active session |
| GET | `/auth/security` | List MFA state, active devices, and recent security events |
| POST / DELETE | `/auth/mfa/*` | Enroll, confirm, or disable TOTP MFA and recovery codes |
| POST | `/auth/reauthenticate` | Rotate the session after password and MFA step-up authentication |
| POST | `/auth/sessions/revoke-others` | Sign out every other device |
| POST | `/auth/sessions/revoke-all` | Sign out every device including the current one |
| GET | `/authorization/access-review` | Report stale, broad, unused, and privileged access risks |
| GET | `/authorization/permissions` | List the human application-permission catalog |
| POST / GET | `/roles` | Create roles or list compact, searchable, paginated role directory entries |
| GET / PATCH / DELETE | `/roles/{id}` | Read, update, or delete an unassigned role |
| GET | `/authorization/assignment-fields` | List compact assignment-field scope options for role administration |
| GET | `/authorization/role-candidates` | Search a bounded role-option catalog for filters and user assignment |
| GET | `/authorization/employee-candidates` | Search visible, unlinked employees for account linking |
| POST / GET | `/users` | Provision users or list compact, searchable, paginated user directory entries |
| GET / PATCH / DELETE | `/users/{id}` | Read, update, or disable a human user |
| POST | `/users/{id}/reset-password` | Set a temporary password and revoke active sessions |
| GET | `/auth/scopes` | List supported operation scopes |
| POST / GET | `/auth/credentials` | Issue a credential once or list safe credential metadata |
| DELETE | `/auth/credentials/{id}` | Revoke a credential |
| POST / GET | `/employees` | Create or list employees |
| GET | `/employees/manager-candidates` | Search a bounded, visibility-scoped set of valid manager choices |
| GET | `/employees/reference-data` | Read distinct department and employee-type values visible to the caller |
| GET / PATCH / DELETE | `/employees/{id}` | Read an employee with a manager summary, or update or delete the employee |
| GET | `/employees/{id}/assignments` | Read compact current assignment cards, or cards at an optional `as_of` UTC timestamp |
| GET | `/employees/{id}/assignments/history` | Read paginated, compact inactive assignment rows by default; use `status=all` for the complete timeline |
| GET | `/employees/{id}/assignment-summary` | Summarize one employee's assignments for a date |
| POST | `/employees/{id}/refresh` | Recompute matching policies and assignments |
| POST | `/assignment-queries` | Query recorded past, persisted present, or calculated future assignments for an employee batch |
| GET | `/assignment-summary` | Summarize assignment coverage across the employee population |
| POST | `/change-previews` | Simulate a supported mutation and return assignment differences without persisting it |
| GET / POST | `/employees/{id}/overrides` | List or create manual overrides |
| GET | `/employees/{id}/overrides/options` | List the visible assignment-field options available to an override manager |
| PATCH / DELETE | `/employees/{id}/overrides/{override_id}` | Update or remove an override |
| POST / GET | `/groups` | Create or list groups |
| GET / PATCH | `/groups/{id}` | Read or update a group |
| GET | `/groups/{id}/employees` | List group members |
| PATCH | `/groups/{id}/employees` | Apply a batch of group member additions and removals atomically |
| POST / DELETE | `/groups/{id}/employees/{employee_id}` | Add or remove a group member |
| GET | `/groups/{id}/policies` | List policies attached to a group |
| POST / DELETE | `/groups/{id}/policies/{policy_id}` | Attach or remove a group policy |
| POST / GET | `/assignment-fields` | Create or list assignment field definitions |
| GET / PATCH | `/assignment-fields/{id}` | Read a field or maintain its value-input contract |
| GET | `/condition-fields` | List system-supported condition fields and dependencies |
| GET | `/condition-fields/{key}` | Read one system-supported condition field |
| POST / GET | `/policies` | Create policies with version 1 or list them |
| GET / PATCH | `/policies/{id}` | Read or update stable policy metadata |
| GET / POST | `/policies/{id}/versions` | List or create policy versions |
| GET | `/policies/{id}/versions/{version_id}` | Read one policy version |
| GET | `/policies/{id}/impact-summary` | Explain a policy's matching and selected-assignment impact |
| GET | `/audit-logs` | Read authorized, filterable audit events |
| GET | `/audit-logs/facets` | Read distinct visible audit entity types and actions for filter controls |

### Collection filtering and pagination

Every `GET` collection endpoint accepts `limit` (default `100`, maximum `500`)
and `offset` (default `0`). Response bodies are arrays. Pagination metadata is returned in `X-Total-Count`, `X-Limit`,
and `X-Offset`; the total is calculated after filters and before pagination.
All collections use a stable ID-based order, with domain-specific secondary
ordering for versions, assignments, and audit events. OpenAPI documents both
the query parameters and response headers.

Available filters include:

- employees: `search`, `state`, `department`, `employee_type`, `location`,
  `manager_id`, `has_manager`, `start_date_from`, and `start_date_to`
- policies: `search`, `status`, `created_from`, and `created_to`; versions also
  support `effective_on`, `priority`, and `created_by`
- groups: `search`; group members support employee population filters and group
  policies support `search` and `status`
- assignment and condition-field catalogs: `search` plus their type,
  cardinality, data type, or active-state fields
- employee assignments and history: assignment field, value, source, and
  effective-time filters; overrides support assignment field and value
- audit events: entity, actor, action, timestamp range, and `search`
- credentials: `search`, `subject`, `scope`, and `status`; operation scopes
  support `search`

`search` is case-insensitive and matches the endpoint's user-facing text
columns. Employee search recognizes both state names and their two-letter
codes. The exact `state` filter accepts only a canonical two-letter code.
`GET /employees/reference-data` exposes the complete grouped state catalog;
employee and state-policy writes reject values outside that catalog. Exact
filters compose with one another using AND semantics. Batch and
mutation results such as `POST /assignment-queries`, refresh, and preview are
explicitly bounded by their request contracts and are not treated
as pageable resource collections.

## Assignment and policy impact summaries

`GET /assignment-summary` aggregates assignment coverage across the employee
population. `GET /employees/{id}/assignment-summary` returns the same contract
for one employee. The response separates policy-derived and override-derived
assignment counts and groups results by assignment field, including assigned
employee counts, distinct-value counts, and a bounded sample of values.

Assignment summaries use recorded assignment history for a past date, current
persisted assignments for today, and stateless resolution for a future date.
Future conflicts do not fail the complete summary: affected employees are
reported in a bounded `conflicts` sample, `conflicted_employee_count` contains
the complete count, and `complete: false` makes the partial nature explicit.
Conflicted employees are excluded from both the assigned and unassigned counts
because their result is unresolved.

`GET /policies/{id}/impact-summary` answers several distinct questions:

- how many employees match the policy directly, through a group, or through
  both origins
- how many employees and assignment values actually select this policy after
  priority and cardinality resolution
- how many selected policy assignments are suppressed by manual overrides
- how many matched employees receive no assignment from the policy because a
  competing policy wins
- which output fields and configured values the effective version contributes
- whether conflicts prevent a complete impact calculation

Policy impact is available for today and future dates. It runs live resolution
against current employee facts, current group membership, and the policy version
effective on the requested date; the response identifies this explicitly as
`live_resolution_current_employee_facts`. Historical employee attributes are not
versioned, so past policy-impact requests return `422` rather than presenting an
inaccurate reconstruction. An archived policy or effective-date gap returns an
explicit `effective: false` summary with zero reach.

Value samples are capped at 20 per field and conflict details at 100 employees;
the corresponding total counts and truncation flags remain exact. These bounds
keep UI and MCP responses predictable even for large populations.

Employee creation and ordinary scalar updates automatically recalculate that employee. A reporting change additionally recalculates the old and new managers and the moved employee's complete subtree, deduplicating all affected IDs at one reconciliation timestamp. Deleting an employee clears direct reports' manager references, cancels that employee's pending reconciliation events, and recalculates the affected reporting subtree. Creating a policy, adding a version, or changing its active/archived status synchronously recalculates every employee in the same transaction. A policy rule can make previously unaffected employees start matching, so the current-scale implementation conservatively scans all employees; this candidate set can be optimized later. Name-only policy changes do not reconcile because they cannot affect results.

Adding or removing a group membership recalculates the affected employee immediately. Attaching or removing a group policy recalculates every current member of that group in the same transaction. If resolution finds an equal-priority conflict, the employee, group, or policy mutation and all partial reconciliation and audit changes are rolled back together.

An active group policy with a currently effective version applies because of the explicit group link, even when that version's condition tree does not match the member directly. Archived, expired, and not-yet-effective group policies are excluded from current `EmployeePolicy` links. If a policy applies directly and through one or more groups, it is still considered only once. Policy origin can be derived from the membership and group-policy links; final assignments record the winning `source_policy_version_id`.

Creating, updating, or removing an override recalculates only the employee's assignments; it does not rerun policy matching. Normal assignments have a `source_policy_version_id`, overridden assignments have a `source_override_id`, and a database check constraint requires exactly one of those sources. Override updates return a new override ID because the previous row is retired for provenance.

Reconciliation is chronological and persists assignment history. Calls older than the latest stored assignment start are rejected instead of rewriting established history. `GET /employees/{id}/assignments` returns the values effective now by default; `as_of` uses half-open interval boundaries. The history endpoint returns inactive rows by default; `status=all` includes both open and closed rows.

`POST /assignment-queries` accepts `employee_ids` and an `evaluation_date`. It
deduplicates the batch and returns one of three explicit modes:

- `recorded_history` for a past date, using persisted assignment rows at the
  start of that UTC date.
- `current_persisted` for today, using the current assignment projection.
- `calculated_future` for a future date, rerunning matching, effective policy
  version selection, conditions, conflict resolution, and active overrides
  without persistence.

Future calculation uses the employee facts, reporting relationships, group
links, policy active/archive status, and unretired overrides currently stored.
Policy-version effective ranges and date-derived facts such as tenure use the
requested evaluation date. Scheduling future employee facts, group changes,
policy status changes, or time-bounded overrides remains outside version 1.
Assignment values in every mode include an `explanation`: recorded history and
current state load the saved snapshot, while calculated future results return a
new, unpersisted snapshot for the requested evaluation date.

## Change preview contract

`POST /change-previews` accepts a discriminated change request and runs the same
domain mutation and reconciliation services used by real writes inside a
database savepoint that is always rolled back. It supports employee creation and
updates, policy creation, policy-version creation, policy lifecycle changes,
group membership changes, and override creation, updates, and deletion.

Policy creation and policy-version creation return the shared, display-focused
`PolicyAssignmentPreviewRead` response. It contains the affected employees with
their IDs, names, and departments; the normalized assignments per match; and a
nullable conflict message. Other change types retain their assignment-detail
responses with before and after assignments, added and removed assignments,
field-level changes, warnings, and conflicts. Proposed employees have a null
employee ID; assignments supplied by a proposed override have a null source ID
and `source_is_proposed: true`. Domain rows, policy links, assignment history,
audit logs, and scheduled reconciliation records are not retained after a
preview.

## Authentication, roles, and operation scopes

Authorization is deliberately capability-oriented. Human sessions use the
fine-grained permission catalog exposed by `GET /authorization/permissions`.
Permissions are allow-only, roles can be combined, and Root implicitly has `*`.
The backend remains authoritative; the frontend uses the same effective list to
hide inaccessible navigation and mutation controls. OpenAPI publishes
`x-required-permissions` for every protected operation.

Machine API credentials retain their separate, coarse operation scopes so
automation clients can support non-user workloads:

- `read`: employees, policies, groups, rule-builder catalogs, and assignments
- `preview`: non-persisting change simulations
- `execute`: ordinary mutations
- `audit`: audit-log reads
- `credentials:manage`: credential creation, listing, and revocation
- `actor:override`: authorized use of `X-Actor` for delegated attribution

`POST /assignment-queries` is a read despite using POST. Preview access is
separate from mutation access. Credential administration
and audit access are also isolated from ordinary reads and writes. Missing,
invalid, expired, or revoked credentials return a structured `401`; insufficient
scope returns a structured `403` containing the required and granted scopes.
OpenAPI also exposes the bearer scheme and an `x-required-scopes` value on every
protected operation, so generated clients and MCP tooling can explain and
enforce the machine boundary.

Interactive MCP access uses the standard OAuth authorization-code flow with S256
PKCE, rotating refresh tokens, revocation, and RFC 9207 issuer binding. Current
clients may identify themselves with an HTTPS Client ID Metadata Document;
dynamic client registration remains available for compatibility with older MCP
clients. An OAuth access token resolves to a normal `User` on every request. The
backend reloads that user's current permissions, employee scope,
assignment-field scope, account status, and password lifecycle before applying
the operation. Cookie and OAuth authentication are therefore two credential
transports for the same user authorization model. Machine API credentials remain
service identities with their existing coarse scopes.

OAuth discovery is published at `/.well-known/oauth-authorization-server`.
`OAUTH_AUTHORIZATION_URL` is the client-facing endpoint on the authorization
server origin and defaults to `/oauth/authorize/start`. That endpoint preserves
the OAuth request and opens the frontend consent screen configured by
`OAUTH_AUTHORIZATION_UI_URL`. Token, registration, revocation, and user-info
endpoints remain on the backend. Configure those values together with
`OAUTH_ISSUER_URL` and `MCP_PUBLIC_URL`; production authorization endpoints must
use HTTPS.

## Error contract

Authentication (`401`), authorization (`403`), not-found (`404`), conflict (`409`), validation (`422`), and service (`5xx`) responses include a stable `error`
object for the UI and MCP clients. It contains a category, application-level
code, human-readable message, and one or more issues with a machine-readable
code, request or domain path, and structured metadata. Request validation issues
preserve Pydantic's error code and exact input location. Policy-assignment
conflicts additionally identify the assignment field, winning priority, and all
conflicting policy/version/value candidates. Change previews return the same
conflict issue shape in their `conflicts` collection.

## Auditing contract

The current action vocabulary is:

- `Policy`: `created`, `changed`, `archived`
- `PolicyVersion`: `created`; `before` is the preceding version snapshot when one exists
- `Group`: `created`, `changed`, `employee_added`, `employee_removed`, `policy_attached`, `policy_detached`
- `Employee`: `created`, `changed`, `manager_changed`, `deleted`
- `EmployeeOverride`: `created`, `changed`, `removed`
- `EmployeeAssignment`: `created`, `ended`
- `APICredential`: `created`, `revoked`; token hashes are excluded from snapshots

An assignment replacement is intentionally two events: `ended` for the old assignment followed by `created` for the replacement. Unchanged reconciliation results and idempotent group operations produce no events.

Snapshots contain JSON-safe mapped scalar values for the affected entity. Policy-version snapshots additionally contain field values and compiled clauses; assignment snapshots include the field name. Scalar dates and timestamps use ISO 8601 strings. The shared snapshot helper automatically replaces columns named `password`, `token`, `access_token`, `api_key`, or `secret` with `[REDACTED]`, and callers must explicitly redact any other sensitive fields introduced later. Audit payloads must never contain credentials or unnecessary employee data.

`GET /audit-logs` supports `entity_type`, `entity_id`, `actor`, `action`, `from_timestamp`, `to_timestamp`, and cross-field `search` filters, plus the shared bounded pagination contract. Results are chronological. There is no mutation or deletion endpoint: audit records are append-only and retained indefinitely in version 1. Any future retention process must be explicitly approved, documented, and run outside ordinary domain mutation paths.

## Scheduled reconciliation contract

`ScheduledReconciliation` contains `entity_type`, `entity_id`, `trigger_type`, `scheduled_at`, `status`, and `processed_at`. An indexed `(status, scheduled_at)` lookup lets a future worker find pending work without scanning policy versions, employees, or overrides. Exact event identity is unique, so scheduling the same event repeatedly is idempotent.

Policy scheduling is maintained immediately whenever a version is created or policy status changes:

- A future `effective_from` creates a `PolicyVersion/becomes_effective` event.
- An inclusive `effective_until` creates a `PolicyVersion/expires` event at the start of the next UTC day.
- Closing a prior open-ended version creates its expiration event at the new version's boundary.
- Archiving a policy cancels its pending events; reactivation restores future events without duplicating rows.

Tenure scheduling is also maintained immediately. Employee creation, `start_date` changes, policy creation/versioning, and policy archive/reactivation recompute desired future anniversary events. Stale pending events are cancelled and exact desired events are created or restored idempotently. `>= N years` changes at anniversary `N`; `> N` and `<= N` change at anniversary `N + 1`; equality schedules both its entry and exit anniversaries. Events outside the policy version's effective range are omitted because version-boundary reconciliation already covers those changes.

`reconcile_due_events()` is the callable processing boundary for the worker. It locks and loads one due batch, deduplicates simultaneous events belonging to the same policy, invokes the existing policy or employee reconciliation paths, and marks events processed only after successful reconciliation. Domain mutations, assignments, audit entries, and schedule status share one transaction; a conflict rolls everything back and leaves the event pending for retry.

The service creates employee tenure-threshold events and also defines dispatch types for future override activation/expiration. Time-bounded override schedule creation remains deferred. No internal timer invokes the processor automatically; the one-shot worker is intended to be called by an external scheduler.

## Reconciliation worker

The project includes a PostgreSQL-only, one-shot worker command:

```bash
DATABASE_MODE=real DATABASE_URL=postgresql+psycopg://user:password@host/database \
uv run python -m app.workers.reconciliation
```

The worker does not create tables or discover future dates from domain tables. It expects the application schema to exist, obtains a PostgreSQL advisory lock so overlapping invocations cannot run, and repeatedly calls `reconcile_due_events()` in independent transactions until the due queue is drained or its runtime budget is reached. `FOR UPDATE SKIP LOCKED` protects claimed event rows. A failed batch rolls back and makes the command exit unsuccessfully while its events remain pending.

Configuration:

- `RECONCILIATION_BATCH_SIZE`: due events per transaction; default `50`
- `RECONCILIATION_MAX_RUNTIME_SECONDS`: maximum drain time; default `900`
- `RECONCILIATION_ADVISORY_LOCK_KEY`: positive PostgreSQL advisory-lock key
- `LOG_LEVEL`: standard Python log level; default `INFO`

The command exits successfully without processing when another invocation owns the advisory lock. It is designed to be invoked hourly by an external scheduler; it does not contain an internal timer or sleep loop.

## Alice example

Create `pay_schedule` (`one`) and `application_access` (`many`). Create a priority-20 policy whose initial version is conditioned on California (`CA`) and produces `biweekly` and `payroll_app`, and a priority-10 policy whose initial version is conditioned on Engineering and produces `weekly` and `GitHub`. Creating Alice in California (`CA`) Engineering automatically resolves:

```text
pay_schedule = biweekly
application_access = payroll_app
application_access = GitHub
```

Patching Alice's state to Wisconsin (`WI`) removes the California policy match and automatically leaves `weekly` and `GitHub`. The integration tests exercise this exact lifecycle.

## Current boundaries

Roles can grant all, selected, or no assignment fields; grants combine by union and update sessions immediately. New roles default to no employee or assignment-field scope until access is chosen explicitly. The scope is enforced across catalogs, complete-policy reads and writes, assignments and history, overrides, queries, summaries, group-policy links, previews, and audit events. Root and machine credentials retain global access. Mixed-domain policies are hidden unless every output domain is allowed so a limited administrator cannot partially inspect or mutate one through another route.

Assignment fields enforce their value contract for policies, previews, and manual overrides. Controlled fields accept only declared options; free text must be selected explicitly when defining a field. This phase still excludes per-policy exceptions, delegated limits on which roles an access administrator may grant, password-reset delivery, MFA, and external identity-provider integration. The domain engine also still excludes retroactive assignment-history rewriting, scheduled future employee facts and relationship changes, time-bounded overrides, override reasons and authorship, administrator-defined condition formulas, an internal worker timer or deployment scheduler, queues, and caching. API credentials remain intended for the MCP server and automation rather than browser users.
